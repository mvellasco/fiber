from datetime import datetime

import falcon

from pony.orm import (
    db_session,
    commit,
    desc,
    Database,
    PrimaryKey,
    Required,
    Optional,
    Set,
    OptimisticCheckError,
    TransactionIntegrityError,
)


db = Database()
db.bind(provider="postgres", user="postgres", password="postgres", host="db", database="banco")


class Client(db.Entity):
    id = PrimaryKey(int, auto=False)
    limit = Required(int)
    balance = Required(int)
    transactions = Set("Transaction", reverse="id_do_cliente")

    def last_10_transactions(self):
        return Transaction.select(id_do_cliente=self.id).order_by(desc(Transaction.date_added))[:10]


class Transaction(db.Entity):
    id = PrimaryKey(int, auto=True)
    id_do_cliente = Required("Client", index=True, reverse="transactions")
    valor = Required(int)
    tipo = Required(str)
    date_added = Required(datetime, default=datetime.now())
    descricao = Optional(str)

    def to_dict(self):
        return {
            "valor": self.valor,
            "descricao": self.descricao,
            "tipo": self.tipo,
            "realizada_em": datetime.now().isoformat()
        }


def initialize_database():
    """TODO: docstring here."""
    db.generate_mapping(create_tables=True)

    # Create and initialize clients.
    limits = {1: 100000, 2: 80000, 3: 1000000, 4: 10000000, 5: 500000}
    for cid, limit in limits.items():
        try:
            with db_session:
                client = Client(id=cid, limit=limit, balance=0)
        except TransactionIntegrityError:
            with db_session:
                client = Client[cid]
                client.limit = limit
                client.balance = 0
            with db_session:
                Transaction.select().delete()


def ingest_transaction(client, transaction):
    if transaction.tipo == "c":
        client.balance += transaction.valor
    elif transaction.tipo == "d":
        client.balance -= transaction.valor

    return None


def get_client_transactions(client_id, limit=None):
    with db_session:
        if limit is not None:
            return Transaction.select(id_do_cliente=client_id)[:limit - 1]
        return Transaction.select(id_do_cliente=client_id)


class BalanceResource:
    """TODO: docstring here."""
    @db_session
    def on_get(self, req, resp, client_id):
        try:
            client = Client[client_id]
        except Exception:
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
    """TODO: Docstring here."""
    def on_post(self, req, resp, client_id):
        try:
            with db_session:
                client = Client[client_id]
        except Exception:
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

        if data["tipo"] == "d" and (abs(client.balance) + data["valor"]) > client.limit:
            resp.status = falcon.HTTP_422
            resp.media = {"status": 422, "detail": "Nao foi possivel adicionar a transacao"}

            return resp

        try:
            with db_session:
                client = Client[client_id]
                transaction = Transaction(**data, id_do_cliente=client_id)
                ingest_transaction(client, transaction)
        except OptimisticCheckError:
            pass

        resp.media = {"saldo": client.balance, "limite": client.limit}
        resp.status = 200

        return resp


def create_app():
    app = falcon.App()
    initialize_database()
    app.add_route('/clientes/{client_id:int}/transacoes', TransactionResource())
    app.add_route('/clientes/{client_id:int}/extrato', BalanceResource())

    return app
