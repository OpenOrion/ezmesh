
from dataclasses import dataclass
from typing import Optional, Protocol, Sequence
import gmsh
import numpy as np
import numpy.typing as npt
from ezmesh.geometry.entity import MeshContext, GeoEntity
from ezmesh.geometry.point import Point
from ezmesh.utils.types import NumpyFloat

class Edge(GeoEntity, Protocol):
    label: Optional[str] = None
    "physical group label"

    start: Point
    "starting point of edge"

    end: Point
    "ending point of edge"

    def get_coords(self, num_pnts: int, is_cosine_sampling: bool = False) -> npt.NDArray[NumpyFloat]:
        ...

PointTuple = tuple[npt.NDArray[NumpyFloat], float]

@dataclass
class Line(Edge):
    start: Point
    "starting point of line"

    end: Point
    "ending point of line"

    label: Optional[str] = None
    "physical group label"

    def before_sync(self, ctx: MeshContext):        
        start_tag = self.start.before_sync(ctx)
        end_tag = self.end.before_sync(ctx)
        
        if (start_tag, end_tag) in ctx.line_registry:
            self.tag = ctx.line_registry[(start_tag, end_tag)]
        else:
            self.tag = gmsh.model.geo.add_line(self.start.tag, self.end.tag)
            ctx.line_registry[(start_tag, end_tag)] = self.tag
        return self.tag

    def after_sync(self, ctx: MeshContext):
        return super().after_sync(ctx)

    def get_coords(self):
        return np.array([self.start.coord, self.end.coord])


@dataclass
class Curve(Edge):
    ctrl_pnts: Sequence[Point]
    "control points of spline"

    type: str
    "type of curve"

    label: Optional[str] = None
    "physical group label"

    tag: Optional[int] = None
    "tag of curve"

    @property
    def start(self):
        return self.ctrl_pnts[0]
    
    @property
    def end(self):
        return self.ctrl_pnts[-1]

    def before_sync(self, ctx: MeshContext):
        ctrl_pnt_tags = [ctrl_point.before_sync(ctx) for ctrl_point in self.ctrl_pnts]

        if self.tag is None:
            if self.type == "BSpline":
                self.tag = gmsh.model.geo.add_bspline(ctrl_pnt_tags)
            elif self.type == "Spline":
                self.tag = gmsh.model.geo.add_spline(ctrl_pnt_tags)
            elif self.type == "Bezier":
                self.tag = gmsh.model.geo.add_bezier(ctrl_pnt_tags)
            else:
                raise ValueError(f"Curve type {self.type} not specified")
        return self.tag
    
    def after_sync(self, ctx: MeshContext):
        return super().after_sync(ctx)

    def get_coords(self, num_pnts: int, is_cosine_sampling: bool):
        ...
        # ctrl_point_coords = np.array([ctrl_point.coord for ctrl_point in self.ctrl_pnts])
        # sampling = get_sampling(num_pnts, is_cosine_sampling)
        # bspline = get_bspline(ctrl_point_coords, 3)
        # return bspline(sampling)

