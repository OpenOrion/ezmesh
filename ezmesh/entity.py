
from dataclasses import dataclass
from enum import Enum
from typing import Literal, Optional, Protocol, Union


EntityTypeString = Literal["compound", "solid", "shell", "face", "wire", "edge", "vertex"]

class EntityType(Enum):
    vertex = 0
    edge = 1
    wire = 1.5
    face = 2
    shell = 2.5
    solid = 3
    compound = 3.5

    @staticmethod
    def resolve(target: Union[EntityTypeString, "EntityType"]):
        if isinstance(target, EntityType):
            return target
        return EntityType[target]

@dataclass
class Entity:
    type: EntityType
    "dimension type of the entity."
    
    tag: int = -1
    "tag of the entity."

    name: Optional[str] = None
    "name of the entity."

    def __eq__(self, __value: object) -> bool:
        if isinstance(__value, Entity):
            return self.type == __value.type and self.tag == __value.tag
        return False

    def __hash__(self) -> int:
        return self.tag
    
class EntityTransaction(Protocol):
    entities: set[Entity]
    is_commited: bool
    is_generated: bool
    def before_gen(self):
        "completes transaction before mesh generation."
        ...

    def after_gen(self):
        "completes transaction after mesh generation."
        ...