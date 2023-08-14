import gmsh
import numpy as np
from dataclasses import dataclass
from typing import Optional, Sequence, cast
from ezmesh.geometry.transaction import GeoContext, DimType, GeoEntity
from ezmesh.geometry.transactions.point import Point
from ezmesh.utils.shapes import get_sampling
from ezmesh.utils.types import NumpyFloat
from cadquery.occ_impl.shapes import Geoms

class Curve(GeoEntity):
    def __init__(self, points: Sequence[Point], tag: int = -1, label: Optional[str] = None) -> None:
        super().__init__(DimType.CURVE, tag, label)
        self.points = points

    @property
    def curves(self):
        return [self]

    @staticmethod
    def _gmsh_add_edge(curve: "Curve", pnt_tags: list[int]) -> int:
        if curve.tag == -1:
            raise NotImplementedError("'Curve' only works with OCP initialized shapes")
        return curve.tag

    def before_sync(self, ctx: GeoContext):
        try:
            cache_curve = ctx.get(self)
            self.tag = cast(int, cache_curve.tag)
        except:  
            if not self.is_synced:
                pnt_tags = [point.before_sync(ctx) for point in self.points]
                self.tag = Curve._gmsh_add_edge(self, pnt_tags)
                ctx.add(self)
        return self.tag

    def after_sync(self, ctx: GeoContext):
        for point in self.points:
            point.after_sync(ctx)

    def get_coords(self, num_pnts: int = 20, is_cosine_sampling: bool = False):
        if self.tag is None:
            return np.array([point.coord for point in self.points])
        
        assert self.tag is not None, "Curve must be synced before getting coordinates"
        bounds = gmsh.model.getParametrizationBounds(DimType.CURVE.value, self.tag)
        sampling = get_sampling(bounds[0][0], bounds[1][0], num_pnts, is_cosine_sampling)
        coords_concatted = gmsh.model.getValue(DimType.CURVE.value, self.tag, sampling)
        coords = np.array(coords_concatted, dtype=NumpyFloat).reshape((-1, 3))

        return coords

@dataclass
class Line(Curve):
    start: Point
    "start point of the line"

    end: Point
    "end point of the line"

    label: Optional[str] = None
    "physical group label"

    tag: int = -1
    "tag of the surface"

    def __post_init__(self):
        super().__init__(points=[self.start, self.end])

    @staticmethod
    def _gmsh_add_edge(curve: Curve, pnt_tags: list[int]) -> int:
        return gmsh.model.occ.add_line(pnt_tags[0], pnt_tags[1], curve.tag)


@dataclass
class Spline(Curve):
    type: Geoms
    "type of curve"

    ctrl_points: Sequence[Point]
    "control points of the curve"

    label: Optional[str] = None
    "physical group label"

    tag: int = -1
    "tag of the surface"

    def __post_init__(self):
        super().__init__(points=self.ctrl_points)

    @staticmethod
    def _gmsh_add_edge(curve: Curve, pnt_tags: list[int]) -> int:
        spline = cast(Spline, curve)
        if spline.type == "BEZIER":
            return gmsh.model.occ.addBezier(pnt_tags, spline.tag)
        elif spline.type == "BSPLINE":
            return gmsh.model.occ.addBSpline(pnt_tags, spline.tag)
        elif spline.type == "SPLINE":
            return gmsh.model.occ.addSpline(pnt_tags, spline.tag)
        else:
            raise NotImplementedError(f"Spline type {spline.type} not implemented")


@dataclass
class Circle(Curve):
    center: Point
    "center of the circle"

    radius: float
    "radius of the circle"

    angle: float = 2 * np.pi
    "angle of the circle"

    label: Optional[str] = None
    "physical group label"

    tag: int = -1
    "tag of the surface"

    def __post_init__(self):
        super().__init__(points=[self.center])

    @staticmethod
    def _gmsh_add_edge(curve: Curve, pnt_tags: list[int]) -> int:
        circle = cast(Circle, curve)
        return gmsh.model.occ.add_circle(circle.center.x, 
            circle.center.y, 
            circle.center.z, 
            circle.radius, 
            circle.tag
        )
