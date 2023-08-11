from typing import Iterable, Optional
from ezmesh.utils.types import Number


def norm_coord(iterable: Iterable[Number], round_by: Optional[int] = 5) -> tuple[float, float, float]:
    return tuple(
        round(float(num), round_by) if round_by 
        else num
        for num in iterable # type: ignore
    )
