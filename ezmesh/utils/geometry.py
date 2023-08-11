from typing import Iterable, Optional
import numpy as np
import gmsh
from ezmesh.utils.types import Number


def normalize_coord(iterable: Iterable[Number], round_by: Optional[int] = 5) -> tuple[float, float, float]:
    return tuple(
        round(float(num), round_by) if round_by 
        else num
        for num in iterable # type: ignore
    )

def get_sampling(start: Number, end: Number, num_samples: int, is_cosine_sampling: bool):
    if is_cosine_sampling:
        beta = np.linspace(0.0,np.pi, num_samples, endpoint=True)
        return 0.5*(1.0-np.cos(beta))*(end-start) + start
    else:
        return np.linspace(start, end, num_samples, endpoint=True)