from typing import Iterable, Optional, TypeVar, Union, List, Dict

T = TypeVar('T')
LinePropertyType = Union[List[T], T, Dict[str, T]]


def get_group_name(label: str) -> str:
    if "/" in label:
        return label.split("/")[0]
    return label


def get_line_property(property: Optional[LinePropertyType[T]], index: int, label: Optional[str] = None) -> Optional[T]:
    if property is None:
        return None
    elif isinstance(property, list):
        return property[index]
    elif isinstance(property, dict):
        if label is None:
            return None
        label_wildcard = f"{get_group_name(label)}/*"
        if label in property:
            return property[label]
        elif label_wildcard in property:
            return property[label_wildcard]
        return None
    else:
        return property


def get_selected_labels(selector_label: str, all_labels: List[str]) -> Iterable[str]:
    if selector_label is None:
        return []
    if "/*" in selector_label:
        return filter(lambda x: x.startswith(selector_label.replace("*", "")), all_labels)
    return [selector_label]
