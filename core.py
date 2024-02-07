import uuid

import falcon
from falcon.media.validators import jsonschema

from pony.orm import (
    Database,
    db_session,
    PrimaryKey,
    Required,
    Optional,
    StrArray,
    select,
)


# db = Database()
# db.bind(provider="postgres", user="postgres", password="postgres", host="db", database="banco")


# person_schema = {
#     "type": "object",
#     "properties": {
#         "apelido": {"type": "string"},
#         "nome": {"type": "string"},
#         "stack": {"type": "array", "items": {"type": "string"}}
#     }
# }


# class Person(db.Entity):
#     id = PrimaryKey(uuid.UUID, auto=True)
#     apelido = Required(str)
#     nome = Required(str)
#     nascimento = Required(str)
#     stack = Optional(StrArray)

#     def to_dict(self, *args, **kwargs):
#         """Override to return json serializable data."""
#         data = super().to_dict(*args, **kwargs)
#         data["id"] = str(data["id"])

#         return data

#     @staticmethod
#     def create_person(*args, **kwargs):
#         data = kwargs
#         person = Person(
#             apelido=data.get("apelido"),
#             nome=data.get("nome"),
#             nascimento=data.get("nascimento"),
#             stack=data.get("stack"),
#         )

#         return person

class Transaction:
    __slots__ = ["valor", "tipo", "descricao", "id_do_cliente"]

    def __init__(self, valor, tipo, descricao, id_do_cliente):
        self.valor = valor
        self.tipo = tipo
        self.descricao = descricao
        self.id_do_cliente = id_do_cliente

    def to_dict(self):
        return {"valor": self.valor, "descricao": self.descricao, "tipo": self.tipo}

# db.generate_mapping(create_tables=True)
from collections import deque
from datetime import datetime


transactions = deque(maxlen=100_000)
balances = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
limits = {1: 10000, 2: 80000, 3: 1000000, 4: 10000000, 5: 500000}


def ingest_transaction(transaction):
    if transaction.tipo == "c":
        balances[transaction.id_do_cliente] += transaction.valor
    elif transaction.tipo == "d":
        balances[transaction.id_do_cliente] += transaction.valor

    transactions.append(transaction)

    return None


def get_client_transactions(client_id):
    return filter(lambda transaction: transaction.id_do_cliente == client_id, transactions)


class TransactionResource:
    def on_get(self, req, resp, client_id):
        try:
            balances[client_id]
        except KeyError:
            resp.status = falcon.HTTP_404

            return resp

        balance = {
            "saldo": {
                "total": balances[client_id],
                "limite": limits[client_id],
                "data_extrato": datetime.now().isoformat(),
            },
            "ultimas_transacoes": []
        }

        resp.media = balance

    # @jsonschema.validate(person_schema)
    def on_post(self, req, resp, client_id):
        try:
            balances[client_id]
        except KeyError:
            resp.status = falcon.HTTP_404

            return resp

        data = req.get_media()
        transaction = Transaction(**data, id_do_cliente=client_id)
        ingest_transaction(transaction)

        resp.media = {"saldo": balances[client_id], "limite": limits[client_id]}
        resp.status = 200


def create_app():
    app = falcon.App()
    app.add_route('/clientes/{client_id:int}/transacoes', TransactionResource())
    app.add_route('/clientes/{client_id:int}/extrato', TransactionResource())

    return app
