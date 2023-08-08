
from dataclasses import dataclass
from typing import Optional, Sequence
import gmsh
import numpy as np
import numpy.typing as npt
from ezmesh.utils.types import DimType
from ezmesh.geometry.transaction import MeshContext, GeoEntityTransaction
from ezmesh.geometry.point import Point
from ezmesh.utils.geometry import get_sampling
from ezmesh.utils.types import NumpyFloat

def unit_vector(vector: npt.NDArray[NumpyFloat]) -> npt.NDArray[NumpyFloat]:
    """ Returns the unit vector of the vector.  """
    return vector / np.linalg.norm(vector)

class Edge(GeoEntityTransaction):
    start: Point
    "starting point of edge"

    end: Point
    "ending point of edge"

    def __init__(self):
        self.label = None
        self.type = DimType.CURVE
    
    def before_sync(self, ctx: MeshContext):
        ctx.add_edge(self)

    def after_sync(self, ctx: MeshContext):
        ...

    def get_coords(self, num_pnts: int = 20, is_cosine_sampling: bool = False) -> npt.NDArray[NumpyFloat]:
        assert self.tag is not None, "Edge must be synced before getting coordinates"
        bounds = gmsh.model.getParametrizationBounds(DimType.CURVE.value, self.tag)
        sampling = get_sampling(bounds[0][0], bounds[1][0], num_pnts, is_cosine_sampling)
        coords_concatted = gmsh.model.getValue(DimType.CURVE.value, self.tag, sampling)
        coords = np.array(coords_concatted, dtype=NumpyFloat).reshape((-1, 3))

        is_line = np.all(unit_vector(coords[0] - coords[-1]) == unit_vector(coords[0] - np.median(coords, axis=0)))

        if is_line:
            return np.array([coords[0], coords[-1]])
        return coords


    @staticmethod
    def from_tag(tag: int, ctx: MeshContext):
        if tag in ctx.edges:
            return ctx.edges[tag]
        edge = Edge()
        edge.tag = tag
        start_coord, end_coord = edge.get_coords(2)
        edge.start = Point(start_coord)
        edge.end = Point(end_coord)
        ctx.add_edge(edge)
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
        super().before_sync(ctx)   
        return self.tag

    def get_coords(self, num_pnts: int = 20, is_cosine_sampling: bool = False):
        return np.array([self.start.coord, self.end.coord])

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

        super().before_sync(ctx)   
        return self.tag
    

