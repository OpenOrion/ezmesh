from dataclasses import dataclass
from typing import Optional, Union, cast
import gmsh
import numpy as np
import numpy.typing as npt
from ezmesh.geometry.entity import DimType, GeoEntity, MeshContext
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
        self.type = DimType.POINT
        self.coord = np.asarray(self.coord, dtype=NumpyFloat)
        self.x = cast(Number, self.coord[0])
        self.y = cast(Number, self.coord[1])
        self.z = cast(Number, self.coord[2] if len(self.coord) == 3 else 0)

    def before_sync(self, ctx: MeshContext):
        pnt_key = (self.x, self.y, self.z)

        if self.tag is None:
            if (self.x, self.y, self.z) in ctx.point_tags:
                self.tag = ctx.point_tags[pnt_key]
            else:
                self.tag = gmsh.model.geo.add_point(self.x, self.y, self.z, self.mesh_size)
                ctx.add_point(pnt_key, self.tag)

        return self.tag

    def after_sync(self, ctx: MeshContext):
        return super().after_sync(ctx)