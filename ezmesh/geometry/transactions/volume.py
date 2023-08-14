import gmsh
from dataclasses import dataclass
from typing import Optional, Sequence, cast
from ezmesh.geometry.transactions.plane_surface import PlaneSurface, set_physical_groups
from ezmesh.geometry.transactions.curve import Curve
from ezmesh.geometry.transaction import GeoContext, DimType, GeoEntity
from ezmesh.geometry.transactions.surface_loop import SurfaceLoop



@dataclass
class Volume(GeoEntity):
    surface_loops: Sequence[SurfaceLoop]
    "surface loop of volume"

    label: Optional[str] = None
    "label for physical group volume"

    tag: int = -1
    "tag of entity"

    def __post_init__(self):
        super().__init__(DimType.VOLUME)

    def before_sync(self, ctx: GeoContext):
        if not self.is_synced:
            surface_loop_tags = [surface_loop.before_sync(ctx) for surface_loop in self.surface_loops]
            self.tag = self.tag or gmsh.model.occ.addVolume(surface_loop_tags, self.tag)
        return self.tag

    def after_sync(self, ctx: GeoContext):
        for surface_loop in self.surface_loops:
            surface_loop.after_sync(ctx)
        set_physical_groups(ctx, [*self.curves, *self.surfaces])

    @property
    def curves(self):
        curves: Sequence[Curve] = []
        for surface_loop in self.surface_loops:
            curves += surface_loop.get_curves()
        return curves

    @property
    def surfaces(self):
        surfaces: Sequence[PlaneSurface] = []
        for surface_loop in self.surface_loops:
            surfaces += surface_loop.surfaces
        return surfaces
