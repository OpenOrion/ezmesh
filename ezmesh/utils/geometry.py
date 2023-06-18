from typing import Optional, TypeVar, Union, List, Dict, cast
from scipy.interpolate import BSpline
import numpy as np
import numpy.typing as npt

T = TypeVar('T')
PropertyType = Union[List[T], T, Dict[str, T]]


def get_group_name(selector: str) -> str:
    if "/" in selector:
        return selector.split("/")[0]
    return selector


def get_property(property: Optional[PropertyType[T]], index: int, label: Optional[str] = None, default: T = None) -> T:
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

def get_sampling(num_samples: int, is_cosine_sampling: bool):
    if is_cosine_sampling:
        beta = np.linspace(0.0,np.pi, num_samples, endpoint=True)
        return 0.5*(1.0-np.cos(beta))
    else:
        return np.linspace(0.0, 1.0, num_samples, endpoint=True)


def get_bspline(ctrl_pnts: npt.NDArray, degree: int):
    "get a bspline with clamped knots"
    num_ctrl_pnts = ctrl_pnts.shape[0]
    knots = np.pad(
        array=np.linspace(0, 1, (num_ctrl_pnts + 1) - degree),
        pad_width=(degree, degree),
        mode='constant',
        constant_values=(0, 1)
    )
    return BSpline(knots, ctrl_pnts, degree, extrapolate=False)
