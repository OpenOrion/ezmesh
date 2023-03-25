from typing import Iterable, Optional, TypeVar, Union, List, Dict

T = TypeVar('T')
PropertyType = Union[List[T], T, Dict[str, T]]


def get_group_name(selector: str) -> str:
    if "/" in selector:
        return selector.split("/")[0]
    return selector


def get_property(property: Optional[PropertyType[T]], index: int, selector: Optional[str] = None, default: T = None) -> T:
    if property is None:
        return default
    elif isinstance(property, list):
        return property[index]
    elif isinstance(property, dict):
        if selector is None:
            return default
        label_wildcard = f"{get_group_name(selector)}/*"
        if selector in property:
            return property[selector]
        elif label_wildcard in property:
            return property[label_wildcard]
        return default
    else:
        return property
