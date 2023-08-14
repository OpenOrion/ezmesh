import gmsh
from dataclasses import dataclass
from typing import Optional, Sequence, cast
import numpy as np
from ezmesh.geometry.transaction import GeoContext, DimType, GeoEntity
from ezmesh.geometry.transactions.curve import Curve


@dataclass
class CurveLoop(GeoEntity):
    curves: Sequence[Curve]
    "Lines of curve"

    label: Optional[str] = None
    "physical group label"

    tag: int = -1
    "tag of the curve loop when passing by reference"

    def __post_init__(self):
        super().__init__(DimType.CURVE_LOOP)

    def set_label(self, label: str):
        super().set_label(label)
        for curve in self.curves:
            curve.set_label(label)

    def before_sync(self, ctx: GeoContext):
        if not self.is_synced:
            curve_tags = [curve.before_sync(ctx) for curve in self.curves]
            self.tag = gmsh.model.occ.add_curve_loop(curve_tags, self.tag)
        return self.tag

    def after_sync(self, ctx: GeoContext):
        for curve in self.curves:
            curve.after_sync(ctx)        
