import gmsh
from dataclasses import dataclass
from typing import Optional, Sequence, cast
import numpy as np
from ezmesh.geometry.transaction import GeoContext, DimType, GeoEntity
from ezmesh.geometry.transactions.curve import Curve

@dataclass
class DirectedPath:
    curve: Curve
    "Curve of the path"

    direction: int = 1
    "Direction of the path. 1 for forward, -1 for backward"

    @property
    def end(self):
        return self.curve.end if self.direction == 1 else self.curve.start

    @property
    def start(self):
        return self.curve.start if self.direction == 1 else self.curve.end

def get_sorted_paths(curves: Sequence[Curve]):
    sorted_paths = [DirectedPath(curves[0], 1)]
    curves = list(curves[1:])
    while curves:
        for i, curve in enumerate(curves):
            if np.all(curve.start.coord == sorted_paths[-1].end.coord):
                directed_path = DirectedPath(curve, 1)
                sorted_paths.append(directed_path)
                curves.pop(i)
                break
            elif np.all(curve.end.coord == sorted_paths[-1].end.coord):
                directed_path = DirectedPath(curve, -1)
                sorted_paths.append(directed_path)
                curves.pop(i)
                break
            elif np.all(curve.start.coord == sorted_paths[0].start.coord):
                directed_path = DirectedPath(curve, -1)
                sorted_paths.insert(0, directed_path)
                curves.pop(i)
                break
        else:
            print("Warning: Curves do not form a closed loop")
            curves = []
    return sorted_paths


@dataclass
class CurveLoop(GeoEntity):
    curves: Sequence[Curve]
    "Lines of curve"

    label: Optional[str] = None
    "physical group label"

    tag: int = -1
    "tag of the curve loop when passing by reference"

    def __post_init__(self):
        self.type = DimType.CURVE_LOOP

    def set_label(self, label: str):
        for curve in self.curves:
            curve.set_label(label)
        super().set_label(label)

    def before_sync(self, ctx: GeoContext):
        if not self.is_synced:
            curve_tags = [
                sorted_path.direction*cast(int, sorted_path.curve.before_sync(ctx)) 
                for sorted_path in get_sorted_paths(self.curves)
            ]
            self.tag = gmsh.model.occ.add_curve_loop(curve_tags, self.tag)
        return self.tag

    def after_sync(self, ctx: GeoContext):
        for curve in self.curves:
            curve.after_sync(ctx)        

    def get_coords(self, num_pnts: int = 20, is_cosine_sampling: bool = False):
        coord_groups = []
        for sorted_path in get_sorted_paths(self.curves):
            coord_group = sorted_path.curve.get_coords(num_pnts, is_cosine_sampling)
            if sorted_path.direction == -1:
                coord_group = coord_group[::-1]
            coord_groups.append(coord_group)
        return np.concatenate(coord_groups)

 