import gmsh
from dataclasses import dataclass
from typing import Optional, Sequence
from ezmesh.geometry.transaction import DimType, GeoEntity, GeoContext
from ezmesh.geometry.transactions.plane_surface import PlaneSurface

@dataclass
class SurfaceLoop(GeoEntity):
    surfaces: Sequence[PlaneSurface]
    "Lines of curve"

    label: Optional[str] = None
    "label for physical group surface loop"

    tag: int = -1
    "tag of surface loop"

    def __post_init__(self):
        self.type = DimType.SURFACE

    def before_sync(self, ctx: GeoContext):
        if not self.is_synced:
            surface_loop_tags = [surface.before_sync(ctx) for surface in self.surfaces]
            self.tag = gmsh.model.occ.addSurfaceLoop(surface_loop_tags, self.tag)
        return self.tag

    def after_sync(self, ctx: GeoContext):
        for surface in self.surfaces:
            surface.after_sync(ctx)

    def get_curves(self):
        return [curve for surface in self.surfaces for curve in surface.curves]