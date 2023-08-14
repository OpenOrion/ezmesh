import gmsh
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Optional, Sequence
from ezmesh.mesh.importers import import_from_gmsh
from ezmesh.mesh.mesh import Mesh

class DimType(Enum):
    POINT = 0
    CURVE = 1
    CURVE_LOOP = 1.5
    SURFACE = 2
    SURFACE_LOOP = 2.5
    VOLUME = 3

@dataclass
class Transaction:
    def __post_init__(self):
        self.is_commited: bool = False
        self.is_generated: bool = False

    def before_gen(self):
        "completes transaction before mesh generation."
        ...

    def after_gen(self):
        "completes transaction after mesh generation."
        ...

@dataclass
class Entity:
    dim_type: DimType
    "dimension type of the entity."
    
    tag: int = -1
    "tag of the entity."


class TransactionContext:
    def __init__(self):
        self.physical_groups: dict[tuple[DimType, str], set[int]] = {}
        self.transactions: list[Transaction] = []
        self.mesh: Optional[Mesh] = None

    def add_physical_groups(self, name: str, entites: Sequence[Entity]):
        for entity in entites:
            group_id = (entity.dim_type, name)
            if group_id not in self.physical_groups:
                self.physical_groups[group_id] = set()
            self.physical_groups[group_id].add(entity.tag)

    def add_transaction(self, transaction: Transaction):
        self.transactions.append(transaction)

    def commit(self, dim: int = 3):
        gmsh.model.occ.synchronize()
        for transaction in self.transactions:
            transaction.before_gen()

        for (dim_type, label), group_tags in self.physical_groups.items():
            physical_group_tag = gmsh.model.addPhysicalGroup(dim_type.value, list(group_tags))
            gmsh.model.set_physical_name(dim_type.value, physical_group_tag, label)

        gmsh.model.mesh.generate(dim)

        for i, transaction in enumerate(self.transactions):
            transaction.after_gen()
            self.transactions.pop(i)

        self.mesh = import_from_gmsh()

