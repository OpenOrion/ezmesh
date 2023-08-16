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
        self.physical_groups = OrderedDict[tuple[EntityType, str], SetPhysicalGroup]()
        # self.fields = OrderedDict[tuple[FieldType, Entity], TransfiniteField]()
        # self.transactions = OrderedDict[tuple[EntityType, str], EntityTransaction]()
        self.transactions = []
        self.mesh: Optional[Mesh] = None
    
    # TODO: clean this up
    # def add_transaction(self, transaction: EntityTransaction):
    #     for entity in transaction.entities:
    #         transaction_id = (entity.type, "name")
    #         if transaction_id not in self.transactions:
    #             self.transactions[transaction_id] = transaction
    #         else:
    #             old_transaction = self.transactions[transaction_id]
    #             old_transaction.entities.remove(entity)
    #             self.transactions[transaction_id] = transaction

    def add_physical_group(self, name: str, entities: OrderedSet[Entity]):
        group_id = (entities.first.type, name)
        if group_id not in self.physical_groups:
            self.physical_groups[group_id] = SetPhysicalGroup(entities, name)
        else:
            self.physical_groups[group_id].entities.update(entities)

    def add_transaction(self, transaction: Transaction):
        self.transactions.append(transaction)

    def commit(self, dim: int = 3):
        gmsh.model.occ.synchronize()

        # self.transactions += self.physical_groups.values()
        # self.transactions += self.fields.values()
        for transaction in self.transactions:
            transaction.before_gen()

        gmsh.model.mesh.generate(dim)

        for transaction in self.transactions:
            transaction.after_gen()
        
        self.transactions = []
        self.mesh = import_from_gmsh()

