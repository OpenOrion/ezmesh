
from dataclasses import dataclass
from enum import Enum
from typing import Literal, Optional, Union

import numpy as np

from ezmesh.transaction import Transaction
from ezmesh.utils.types import OrderedSet


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
        return hash((self.type, self.tag))

@dataclass(eq=False)
class SingleEntityTransaction(Transaction):
    entity: Entity
    "The entity that transaction will be applied towards"

@dataclass(eq=False)
class MultiEntityTransaction(Transaction):
    entities: OrderedSet[Entity]
    "The entities that transaction will be applied towards"