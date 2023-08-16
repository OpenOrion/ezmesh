from enum import Enum
from typing import Literal, Union


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
