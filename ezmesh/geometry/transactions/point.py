from dataclasses import dataclass
from typing import Optional, Union, cast
import gmsh
import numpy as np
import numpy.typing as npt
from ezmesh.geometry.transaction import DimType, GeoEntity, GeoContext
from ezmesh.utils.types import NumpyFloat

CoordType = Union[npt.NDArray[NumpyFloat], tuple[float, float], tuple[float, float, float], list[float]]

@dataclass
class Point(GeoEntity):
    coord: CoordType
    "coordinate of point"

    mesh_size: float = 0.0
    "mesh size for point"

    label: Optional[int] = None
    "tag of point"

    tag: int = -1
    "tag of point"

    def __post_init__(self):
        self.type = DimType.POINT
        self.x = self.coord[0]
        self.y = self.coord[1]
        self.z = self.coord[2] if len(self.coord) == 3 else 0
        self.coord = np.array([self.x, self.y, self.z], dtype=NumpyFloat)

    def set_mesh_size(self, mesh_size: float):
        self.mesh_size = mesh_size
            
    def before_sync(self, ctx: GeoContext):
        try:
            cache_pnt = ctx.get(self)
            self.tag = cast(int, cache_pnt.tag)
        except:
            if not self.is_synced:
                self.tag = gmsh.model.occ.add_point(self.x, self.y, self.z, self.mesh_size, self.tag)
                ctx.add(self)

        gmsh.model.occ.mesh.setSize([(self.type.value, self.tag)], self.mesh_size)

        return self.tag

    def after_sync(self, ctx: GeoContext):
        ...
