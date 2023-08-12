from typing import Sequence
import numpy as np
from ezmesh.geometry.transaction import DimType, GeoEntity
from ezmesh.utils.types import Number

def get_sampling(start: Number, end: Number, num_samples: int, is_cosine_sampling: bool):
    if is_cosine_sampling:
        beta = np.linspace(0.0,np.pi, num_samples, endpoint=True)
        return 0.5*(1.0-np.cos(beta))*(end-start) + start
    else:
        return np.linspace(start, end, num_samples, endpoint=True)


def get_physical_group_tags(entities: Sequence[GeoEntity]):
    physical_groups: dict[tuple[DimType, str], list[int]] = {}
    for entity in entities:
        if not entity.label or not entity.tag or entity.is_commited:
            continue
        if (entity.type, entity.label) not in physical_groups:
            physical_groups[(entity.type, entity.label)] = []
        physical_groups[(entity.type, entity.label)].append(entity.tag)
    return physical_groups
