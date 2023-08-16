from enum import Enum
import gmsh
from typing import Optional, OrderedDict
from ezmesh.entity import Entity, EntityTransaction, EntityType
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
    
    def add_transaction(self, transaction: Transaction):
        if isinstance(transaction, EntityTransaction):
            for entity in transaction.entities:
                transaction_id = (type(transaction), entity)
                if transaction_id not in self.entity_transactions:
                    self.entity_transactions[transaction_id] = transaction
                else:
                    old_transaction = self.entity_transactions[transaction_id]
                    assert isinstance(old_transaction, EntityTransaction), "old transaction must be of type EntityTransaction"
                    old_transaction.entities.remove(entity)
                    self.entity_transactions[transaction_id] = transaction
        else:
            self.system_transactions[type(transaction)] = transaction

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

