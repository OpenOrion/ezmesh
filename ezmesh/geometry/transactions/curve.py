
import gmsh
import numpy as np
from dataclasses import dataclass
from typing import Literal, Optional, Sequence, Union, cast
from ezmesh.geometry.transaction import GeoContext, DimType, GeoEntity
from ezmesh.geometry.transactions.point import Point
from ezmesh.utils.shapes import get_sampling
from ezmesh.utils.types import NumpyFloat
from cadquery.occ_impl.shapes import Geoms

@dataclass
class CurveProps(GeoEntity):
    type: Geoms
    "type of curve"

    points: Sequence[Point]
    "control points of the curve"

@dataclass
class CircleProps:
    type: Geoms
    "type of curve"

    center: Point
    "center of the circle"

    radius: float
    "radius of the circle"

    angle: float = 2 * np.pi
    "angle of the circle"

@dataclass
class EllipseProps:
    type: Geoms
    "type of curve"

    center: Point
    "center of the circle"

    radius1: float
    "radius of the circle"

    radius2: float
    "radius of the circle"

    angle: float = 2 * np.pi
    "angle of the circle"


@dataclass
class Curve(GeoEntity):
    props: Union[CurveProps, CircleProps, EllipseProps]
    "properties of the curve"

    label: Optional[str] = None
    "physical group label"

    tag: int = -1
    "tag of the surface"

    def __post_init__(self):
        self.type = DimType.CURVE
        if isinstance(self.props, CurveProps):
            self.points = self.props.points
        else:
            self.points = [self.props.center]
        self.start = self.points[0]
        self.end = self.points[-1]

    @property
    def curves(self):
        return [self]

    def before_sync(self, ctx: GeoContext):
        try:
            cache_curve = ctx.get(self)
            self.tag = cast(int, cache_curve.tag)
        except:  
            if not self.is_synced:
                pnt_tags = [point.before_sync(ctx) for point in self.points]

                if self.props.type == "LINE":
                    self.tag = gmsh.model.occ.add_line(pnt_tags[0], pnt_tags[1], self.tag)
                elif self.props.type == "CIRCLE":
                    assert isinstance(self.props, CircleProps)
                    self.tag = gmsh.model.occ.add_circle(self.props.center.x, self.props.center.y, self.props.center.z, self.props.radius, self.tag)
                elif self.props.type == "ELLIPSE":
                    assert isinstance(self.props, EllipseProps)
                    self.tag = gmsh.model.occ.add_ellipse(self.props.center.x, self.props.center.y, self.props.center.z, self.props.radius1, self.props.radius2, self.tag)
                elif self.props.type == "BEZIER":
                    self.tag = gmsh.model.occ.addBezier(pnt_tags, self.tag)
                elif self.props.type == "BSPLINE":
                    self.tag = gmsh.model.occ.addBSpline(pnt_tags, self.tag)
                elif self.props.type == "SPLINE":
                    self.tag = gmsh.model.occ.addSpline(pnt_tags, self.tag)
                else:
                    print(f"Curve type {self.props.type} not implemented")

                ctx.add(self)
        return self.tag
    

    def get_coords(self, num_pnts: int = 20, is_cosine_sampling: bool = False):
        if self.tag is None:
            return np.array([point.coord for point in self.points])
        
        assert self.tag is not None, "Curve must be synced before getting coordinates"
        bounds = gmsh.model.getParametrizationBounds(DimType.CURVE.value, self.tag)
        sampling = get_sampling(bounds[0][0], bounds[1][0], num_pnts, is_cosine_sampling)
        coords_concatted = gmsh.model.getValue(DimType.CURVE.value, self.tag, sampling)
        coords = np.array(coords_concatted, dtype=NumpyFloat).reshape((-1, 3))

        return coords


