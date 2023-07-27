from dataclasses import dataclass
from typing import Optional, Union
import gmsh
import numpy as np
import numpy.typing as npt
from ezmesh.geometry.entity import GeoEntity, MeshContext
from ezmesh.utils.types import Number, NumpyFloat

CoordType = Union[npt.NDArray[NumpyFloat], tuple[Number, Number], tuple[Number, Number, Number], list[Number]]

@dataclass
class Point(GeoEntity):
    coord: CoordType
    "coordinate of point"

    mesh_size: float = 0.0
    "mesh size for point"

    label: Optional[int] = None
    "tag of point"

    tag: Optional[int] = None
    "tag of point"

    def __post_init__(self):
        super().__init__()
        self.coord = np.asarray(self.coord)
        self.x = self.coord[0]
        self.y = self.coord[1]
        self.z = self.coord[2] if len(self.coord) == 3 else 0

    def before_sync(self, ctx: MeshContext):
        pnt_key = (self.x, self.y, self.z)

        if self.tag is None:
            if (self.x, self.y, self.z) in ctx.point_lookup:
                self.tag = ctx.point_lookup[pnt_key]
            else:
                self.tag = gmsh.model.geo.add_point(self.x, self.y, self.z, self.mesh_size)
                ctx.point_lookup[pnt_key] = self.tag

        return self.tag

    def after_sync(self, ctx: MeshContext):
        return super().after_sync(ctx)