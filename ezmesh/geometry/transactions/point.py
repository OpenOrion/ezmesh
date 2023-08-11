from dataclasses import dataclass
from typing import Optional, Union, cast
import gmsh
import numpy as np
import numpy.typing as npt
from ezmesh.utils.norm import norm_coord
from ezmesh.geometry.transaction import DimType, GeoEntity, Context
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
        self.x = cast(Number, self.coord[0])
        self.y = cast(Number, self.coord[1])
        self.z = cast(Number, self.coord[2] if len(self.coord) == 3 else 0)
        self.coord = np.array([self.x, self.y, self.z], dtype=NumpyFloat)

    def set_mesh_size(self, mesh_size: float):
        self.mesh_size = mesh_size
        if self.tag is not None:
            gmsh.model.geo.mesh.setSize([(self.type.value, self.tag)], self.mesh_size)
            
    def before_sync(self, ctx: Context):
        pnt_key = norm_coord(self.coord, round_by=None)

        if pnt_key in ctx.point_tags:
            self.tag = ctx.point_tags[pnt_key]
        else:
            self.tag = gmsh.model.geo.add_point(self.x, self.y, self.z, self.mesh_size)
            ctx.add_point(self)

        return self.tag

    def after_sync(self, ctx: Context):
        return super().after_sync(ctx)
    
    @property
    def id(self):
        return (self.type, norm_coord(self.coord))