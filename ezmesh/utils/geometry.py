from typing import Iterable, Optional, TypeVar, Union, List, Dict

T = TypeVar('T')
PropertyType = Union[List[T], T, Dict[str, T]]


def get_group_name(selector: str) -> str:
    if "/" in selector:
        return selector.split("/")[0]
    return selector


def get_property(property: Optional[PropertyType[T]], index: int, marker: Optional[str] = None, default: T = None) -> T:
    if property is None:
        return default
    elif isinstance(property, list):
        return property[index]
    elif isinstance(property, dict):
        if marker is None:
            return default
        marker_wildcard = f"{get_group_name(marker)}/*"
        if marker in property:
            return property[marker]
        elif marker_wildcard in property:
            return property[marker_wildcard]
        return default
    else:
        return property
