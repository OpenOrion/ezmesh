
from dataclasses import dataclass
from typing import Optional, Sequence
import gmsh
import numpy as np
import numpy.typing as npt
from ezmesh.geometry.entity import MeshContext, GeoEntity
from ezmesh.geometry.point import Point
from ezmesh.utils.types import NumpyFloat


class Edge(GeoEntity):
    start: Point
    "starting point of edge"

    end: Point
    "ending point of edge"

    label: Optional[str] = None
    "physical group label"        

    def before_sync(self, ctx: MeshContext):
        ...

    def after_sync(self, ctx: MeshContext):
        ...

    def get_coords(self, num_pnts: int = 20) -> npt.NDArray[NumpyFloat]:
        assert self.tag is not None, "Edge must be synced before getting coordinates"
        bounds = gmsh.model.getParametrizationBounds(1, self.tag)
        t = [bounds[0][0] + i * (bounds[1][0] - bounds[0][0]) / num_pnts for i in range(num_pnts)]
        coords_concatted = gmsh.model.getValue(1, self.tag, t)
        return np.array(coords_concatted, dtype=NumpyFloat).reshape((-1, 3))

    @staticmethod
    def from_tag(tag: int):
        edge = Edge()
        edge.tag = tag
        return edge

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
        self.tag = self.tag or gmsh.model.geo.add_line(start_tag, end_tag)
        return self.tag

    def after_sync(self, ctx: MeshContext):
        return super().after_sync(ctx)

    def get_coords(self, num_pnts: int = 2):
        return super().get_coords(num_pnts)

@dataclass
class Curve(Edge):
    ctrl_pnts: Sequence[Point]
    "control points of spline"

    type: str
    "type of curve"

    label: Optional[str] = None
    "physical group label"

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

