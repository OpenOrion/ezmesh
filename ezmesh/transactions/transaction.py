import gmsh
from dataclasses import dataclass
from typing import Optional, Sequence, Union
from ezmesh.utils.gmsh import EntityType
from ezmesh.mesh.importers import import_from_gmsh
from ezmesh.mesh.mesh import Mesh

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
    dim_type: EntityType
    "dimension type of the entity."
    
    tag: int = -1
    "tag of the entity."

    name: Optional[str] = None
    "name of the entity."

    def __eq__(self, __value: object) -> bool:
        if isinstance(__value, Entity):
            return self.dim_type == __value.dim_type and self.tag == __value.tag
        return False

    def __hash__(self) -> int:
        return self.tag

class TransactionContext:
    def __init__(self):
        self.physical_groups: dict[tuple[EntityType, str], set[int]] = {}
        self.transactions: list[Transaction] = []
        self.mesh: Optional[Mesh] = None

    def add_physical_groups(self, name: Union[str, Sequence[str]], entites: Sequence[Entity]):
        for i, entity in enumerate(entites):
            entity.name = name if isinstance(name, str) else name[i]
            group_id = (entity.dim_type, entity.name)
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

        for transaction in self.transactions:
            transaction.after_gen()
        
        self.transactions = []
        self.mesh = import_from_gmsh()

