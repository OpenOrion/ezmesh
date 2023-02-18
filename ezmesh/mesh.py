
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional
import numpy.typing as npt
import numpy as np

class ElementType(Enum):
    LINE = 1
    TRIANGLE = 2
    QUADRILATERAL = 3
    TETRAHEDRON = 4
    HEXAHEDRON = 5
    PRISM = 6
    PYRAMID = 7
    POINT = 15

@dataclass
class Mesh:
    dim: int
    elements: List[npt.NDArray[np.uint16]]
    element_types: List[ElementType]
    points: npt.NDArray[np.float64]
    markers: Dict[str, List[npt.NDArray[np.uint16]]]
