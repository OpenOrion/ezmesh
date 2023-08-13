
import gmsh
import numpy as np
from dataclasses import dataclass
from typing import Literal, Optional, Sequence, cast
from ezmesh.geometry.transaction import GeoContext, DimType, GeoEntity
from ezmesh.geometry.transactions.point import Point
from ezmesh.utils.geometry import get_sampling
from ezmesh.utils.types import NumpyFloat
from cadquery.occ_impl.shapes import Geoms

@dataclass
class Curve(GeoEntity):
    ctrl_pnts: Sequence[Point]
    "control points of spline"

    curve_type: Geoms
    "type of curve"

    radii: Optional[Sequence[float]] = None
    "radii of the curve if circle or ellipse"

    label: Optional[str] = None
    "physical group label"

    tag: int = -1
    "tag of the surface"

    def __post_init__(self):
        self.type = DimType.CURVE
        self.start = self.ctrl_pnts[0]
        self.end = self.ctrl_pnts[-1]

    def before_sync(self, ctx: GeoContext):
        try:
            cache_curve = ctx.get(self)
            self.tag = cast(int, cache_curve.tag)
        except:  
            if not self.is_synced:
                ctrl_pnt_tags = [ctrl_point.before_sync(ctx) for ctrl_point in self.ctrl_pnts]

                if self.curve_type == "LINE":
                    self.tag = gmsh.model.occ.add_line(ctrl_pnt_tags[0], ctrl_pnt_tags[1], self.tag)
                elif self.curve_type == "CIRCLE":
                    assert self.radii is not None, "Radii must be specified for circle"
                    center_pnt = self.ctrl_pnts[0]
                    self.tag = gmsh.model.occ.add_circle(center_pnt.x, center_pnt.y, center_pnt.z, self.radii[0], self.tag)
                elif self.curve_type == "ELLIPSE":
                    assert self.radii is not None, "Radii must be specified for ellipse"
                    center_pnt = self.ctrl_pnts[0]
                    self.tag = gmsh.model.occ.add_ellipse(center_pnt.x, center_pnt.y, center_pnt.z, self.radii[0], self.radii[1], self.tag)
                elif self.curve_type == "BEZIER":
                    self.tag = gmsh.model.occ.addBezier(ctrl_pnt_tags, self.tag)
                elif self.curve_type == "BSPLINE":
                    self.tag = gmsh.model.occ.addBSpline(ctrl_pnt_tags, self.tag)
                elif self.curve_type == "SPLINE":
                    self.tag = gmsh.model.occ.addSpline(ctrl_pnt_tags, self.tag)
                else:
                    print(f"Curve type {self.curve_type} not implemented")

                ctx.add(self)
        return self.tag
    

    def get_coords(self, num_pnts: int = 20, is_cosine_sampling: bool = False):
        if self.tag is None:
            return self.ctrl_pnts
        
        assert self.tag is not None, "Curve must be synced before getting coordinates"
        bounds = gmsh.model.getParametrizationBounds(DimType.CURVE.value, self.tag)
        sampling = get_sampling(bounds[0][0], bounds[1][0], num_pnts, is_cosine_sampling)
        coords_concatted = gmsh.model.getValue(DimType.CURVE.value, self.tag, sampling)
        coords = np.array(coords_concatted, dtype=NumpyFloat).reshape((-1, 3))
        return coords


