import logging
from collections import OrderedDict
from datetime import datetime
from functools import lru_cache

import falcon
import memcache
from pony.orm import db_session, rollback, OperationalError

from fiber.database import Client, Transaction, initialize_database

logger = logging.getLogger(__name__)


class TransactionInterface:
    def __init__(self, valor, tipo, descricao, date_added, client):
        self.valor = valor
        self.tipo = tipo
        self.descricao = descricao
        self.date_added = date_added
        self.client = client

    def to_dict(self):
        return {
            "valor": self.valor,
            "descricao": self.descricao,
            "tipo": self.tipo,
            "date_added": self.date_added.isoformat(),
        }


def _get_db_session(retry=0):
    try:
        yield db_session(serializable=True)
    except OperationalError as exc:
        if retry <= 1_000:
            yield from _get_db_session(retry=retry + 1)
        raise exc


@db_session(retry=100)
def ingest_transaction(client_id, transaction_interface):
    """Ingest a transaction into the database and update the client's balance.

    :param client_id: the id of the client.
    :param transaction: the transaction dto to ingest.
    :return: a tuple with a boolean indicating success and the updated client object.
    """
    client = Client[client_id]

    if transaction_interface.tipo == "c":
        client.balance += transaction_interface.valor
    elif transaction_interface.tipo == "d":
        client.balance -= transaction_interface.valor

    if transaction_interface.tipo == "d" and abs(client.balance) > client.limit:
        rollback()
        return False, None

    invalidate_cache(client_id=client_id)
    Transaction(client=client, **transaction_interface.to_dict())

    return True, client


cache = memcache.Client(['fiber-memcached:11211'], debug=0)


def invalidate_cache(client_id):
    cache.delete(f"client_id_{client_id}")
    return None


def cache_client(func):
    """Cache the client object until manual expiration."""
    def wrapper(client_id):
        if cache.get(f"client_id_{client_id}"):
            return cache.get(f"client_id_{client_id}")

        _result = func(client_id)
        cache.set(f"client_id_{client_id}", _result)

        return _result
    return wrapper


@cache_client
@db_session
def get_client(client_id):
    """Return a client object from the database, filtering by id."""
    return Client[client_id]


class BalanceResource:
    """Handle getting the balance of a client.

    TODO: add more details here.
    """

    def on_get(self, req, resp, client_id):
        try:
            client = get_client(client_id=client_id)
        except Exception as exc:
            logger.exception(f"Exception: {exc}")
            resp.status = falcon.HTTP_404
            resp.media = {"status": 404, "detail": "Cliente nao encontrado"}

            return resp

        balance = {
            "saldo": {
                "total": client.balance,
                "limite": client.limit,
                "data_extrato": datetime.now().isoformat(),
            },
            "ultimas_transacoes": [tx.to_dict() for tx in client.last_10_transactions()]
        }

        resp.media = balance

        return resp


class TransactionResource:
    """Handle creating transactions.

    Uses the db_session decorator to ensure that the transaction is
    properly committed to the database.
    """

    def on_post(self, req, resp, client_id):
        try:
            if client_id not in [1, 2, 3, 4, 5]:
                raise ValueError(f"Client with id #{client_id} not found.")
        except ValueError:
            resp.status = falcon.HTTP_404

            return resp

        data = req.get_media()
        if (
            not all(bool(value) for _, value in data.items())
            or len(data["descricao"]) > 10
            or data["tipo"] not in ["c", "d"]
            or not isinstance(data["valor"], int)
        ):
            resp.status = falcon.HTTP_422
            resp.media = {"status": 422, "detail": "Todos os campos são obrigatórios"}
            
            return resp

        transaction_interface = TransactionInterface(**data, date_added=datetime.now(), client=client_id)
        result, updated_client = ingest_transaction(client_id, transaction_interface)

        if result and isinstance(updated_client, Client):
            resp.status = falcon.HTTP_200
            resp.media = {
                "saldo": updated_client.balance,
                "limite": updated_client.limit,
            }
        else:
            resp.status = falcon.HTTP_422
            resp.media = {"status": 422, "detail": "Transação inválida"}

        return resp


def create_app():
    app = falcon.App()
    initialize_database()
    app.add_route('/clientes/{client_id:int}/transacoes', TransactionResource())
    app.add_route('/clientes/{client_id:int}/extrato', BalanceResource())

    return app
