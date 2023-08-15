from enum import Enum
from typing import Literal


class DimType(Enum):
    POINT = 0
    CURVE = 1
    CURVE_LOOP = 1.5
    SURFACE = 2
    SURFACE_LOOP = 2.5
    VOLUME = 3


class MeshAlgorithm2D(Enum):
    MeshAdapt = 1
    Automatic = 2
    InitialMeshOnly = 3
    Delaunay = 5
    FrontalDelaunay = 6
    BAMG = 7
    FrontalDelaunayQuads = 8
    PackingOfParallelograms = 9
    QuasiStructuredQuad = 11

class MeshAlgorithm3D(Enum):
    Delaunay = 1
    InitialMeshOnly = 3
    Frontal = 4
    MMG3D = 7
    RTree = 9
    HXT = 10


MeshAlgorithm2DType =  Literal["MeshAdapt", "Automatic", "InitialMeshOnly", "Delaunay", "FrontalDelaunay", "BAMG", "FrontalDelaunayQuads", "PackingOfParallelograms", "QuasiStructuredQuad"]
MeshAlgorithm3DType =  Literal["Delaunay", "InitialMeshOnly", "Frontal", "MMG3D", "RTree", "HXT"]
