import gmsh
from dataclasses import dataclass
from ezmesh.entity import Entity
from ezmesh.transaction import Transaction
from ezmesh.utils.types import OrderedSet


@dataclass
class SetPhysicalGroup(Transaction):    
    entities: OrderedSet[Entity]
    "The entities that will be added to the physical group."

    name: str
    "The name of the physical group."

    # TODO: clean this up

    def before_gen(self):
        entity_tags = []
        entity_types = set()
        entity_type = None
        for entity in self.entities:
            entity.name = self.name
            entity_type = entity.type
        
            entity_tags.append(entity.tag)
            entity_types.add(entity.type)
        
        assert len(entity_types) == 1, "All entities must be of the same type"
        physical_group_tag = gmsh.model.addPhysicalGroup(entity_type, entity_tags)
        gmsh.model.set_physical_name(entity_type, physical_group_tag, self.name)