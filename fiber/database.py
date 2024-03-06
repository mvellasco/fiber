from datetime import datetime

from pony.orm import (
    db_session,
    desc,
    Database,
    PrimaryKey,
    Required,
    Optional,
    Set,
    TransactionIntegrityError,
)


db = Database()
db.bind(provider="postgres", user="postgres", password="postgres", host="fiber-db", database="banco")


class Client(db.Entity):
    id = PrimaryKey(int, auto=False)
    limit = Required(int)
    balance = Required(int)
    transactions = Set("Transaction", reverse="client")

    @db_session
    def last_10_transactions(self):
        return self.transactions.order_by(desc(Transaction.date_added))[:9]


class Transaction(db.Entity):
    id = PrimaryKey(int, auto=True)
    client = Required("Client", index=True, reverse="transactions")
    valor = Required(int)
    tipo = Required(str)
    date_added = Required(datetime)
    descricao = Optional(str)

    def to_dict(self):
        return {
            "valor": self.valor,
            "descricao": self.descricao,
            "tipo": self.tipo,
            "realizada_em": self.date_added.isoformat(),
        }


def initialize_database():
    """Generate the database schema and initialize the clients."""
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
