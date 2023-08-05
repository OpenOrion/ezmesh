from enum import Enum
from typing import Union
import numpy as np

NumpyFloat = np.float32
Number = Union[int, float, NumpyFloat]

class DimType(Enum):
    POINT = 0
    CURVE = 1
    SURFACE = 2
    VOLUME = 3
    CURVE_LOOP = 10
