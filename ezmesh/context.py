from enum import Enum
import gmsh
from typing import Optional, OrderedDict, Sequence
from ezmesh.entity import Entity, MultiEntityTransaction, SingleEntityTransaction
from ezmesh.mesh.importers import import_from_gmsh
from ezmesh.mesh.mesh import Mesh
from ezmesh.transaction import Transaction
from ezmesh.transactions.physical_group import SetPhysicalGroup
from ezmesh.utils.types import OrderedSet


class Context:
    def __init__(self):
        self.entity_transactions = OrderedDict[tuple[type[Transaction], Entity], Transaction]()
        self.system_transactions = OrderedDict[type[Transaction], Transaction]()

        self.mesh: Optional[Mesh] = None
    
    def get_transaction(self, transaction_type: type[Transaction], entity: Optional[Entity] = None) -> Optional[Transaction]:
        if entity is None:
            return self.system_transactions.get(transaction_type)
        else:
            return self.entity_transactions.get((transaction_type, entity))

    def add_transaction(self, transaction: Transaction):
        if isinstance(transaction, (SingleEntityTransaction, MultiEntityTransaction) ):
            entities = transaction.entities if isinstance(transaction, MultiEntityTransaction) else OrderedSet([transaction.entity])
            for entity in entities:
                transaction_id = (type(transaction), entity)
                if transaction_id not in self.entity_transactions:
                    self.entity_transactions[transaction_id] = transaction
                else:
                    old_transaction = self.entity_transactions[transaction_id]
                    if isinstance(old_transaction, MultiEntityTransaction):
                        old_transaction.entities.remove(entity)
                    self.entity_transactions[transaction_id] = transaction
        else:
            self.system_transactions[type(transaction)] = transaction

    def add_transactions(self, transactions: Sequence[Transaction]):
        for transaction in transactions:
            self.add_transaction(transaction)

    def commit(self, dim: int = 3):
        gmsh.model.occ.synchronize()
        transactions = OrderedSet([
            *self.entity_transactions.values(),
            * self.system_transactions.values()
        ])
        for transaction in transactions:
            transaction.before_gen()

        gmsh.model.mesh.generate(dim)

        for transaction in transactions:
            transaction.after_gen()
        
        self.entity_transactions = OrderedDict()
        self.system_transactions = OrderedDict()
        self.mesh = import_from_gmsh()

