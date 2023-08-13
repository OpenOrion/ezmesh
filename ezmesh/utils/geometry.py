import gmsh
from typing import Sequence
import numpy as np
from ezmesh.geometry.transaction import DimType, GeoEntity
from ezmesh.utils.types import Number

def get_physical_group_tags(entities: Sequence[GeoEntity]):
    physical_groups: dict[tuple[DimType, str], list[int]] = {}
    for entity in entities:
        if not entity.label or entity.tag == -1 or entity.is_commited:
            continue
        if (entity.type, entity.label) not in physical_groups:
            physical_groups[(entity.type, entity.label)] = []
        physical_groups[(entity.type, entity.label)].append(entity.tag)
    return physical_groups

