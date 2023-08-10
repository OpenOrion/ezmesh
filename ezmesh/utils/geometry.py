from typing import Optional, Sequence, TypeVar, Union, cast
import numpy as np
import gmsh
from ezmesh.geometry.transaction import GeoTransaction, MeshContext
from ezmesh.importers import import_from_gmsh
from ezmesh.utils.types import Number

T = TypeVar('T')
PropertyType = Union[list[T], T, dict[str, T]]


def get_group_name(selectors: Union[str, list[str]]):
    group_names = []
    for selector in (selectors if isinstance(selectors, list) else [selectors]):
        if "/" in selector:
            selector = selector.split("/")[0]
        group_names.append(selector)
    return group_names if len(group_names) > 1 else group_names[0]


def get_property(property: Optional[Union[list[T], T, dict[str, T]]], index: int, label: Optional[str] = None, default: T = None) -> T:
    if property is None:
        return cast(T, default)
    elif isinstance(property, list):
        return property[index]
    elif isinstance(property, dict):
        if label is None:
            return cast(T, default)
        label_wildcard = f"{get_group_name(label)}/*"
        if label in property:
            return property[label]
        elif label_wildcard in property:
            return property[label_wildcard]
        return cast(T, default)
    else:
        return property

def get_sampling(start: Number, end: Number, num_samples: int, is_cosine_sampling: bool):
    if is_cosine_sampling:
        beta = np.linspace(0.0,np.pi, num_samples, endpoint=True)
        return 0.5*(1.0-np.cos(beta))*(end-start) + start
    else:
        return np.linspace(start, end, num_samples, endpoint=True)

def commit_transactions(transactions: Union[GeoTransaction, Sequence[GeoTransaction]], ctx: MeshContext = MeshContext()):
    if isinstance(transactions, Sequence):
        for transaction in transactions:
            transaction.before_sync(ctx)
    else:
        transactions.before_sync(ctx)
    gmsh.model.geo.synchronize()
    if isinstance(transactions, Sequence):
        for transaction in transactions:
            transaction.after_sync(ctx)
    else:
        transactions.after_sync(ctx)

def generate_mesh(transactions: Union[GeoTransaction, Sequence[GeoTransaction]], dim: int = 3, ctx: MeshContext = MeshContext()):
    commit_transactions(transactions, ctx)
    gmsh.option.set_number("General.ExpertMode", 1)

    gmsh.model.mesh.generate(dim)
    
    return import_from_gmsh()

