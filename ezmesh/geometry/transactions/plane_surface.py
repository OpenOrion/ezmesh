import gmsh
from dataclasses import dataclass
from typing import Optional, Sequence, cast
from ezmesh.geometry.transaction import GeoContext, DimType, GeoEntity
from ezmesh.geometry.transactions.curve_loop import CurveLoop
from ezmesh.utils.geometry import get_physical_group_tags


def set_physical_groups(ctx: GeoContext, entities: Sequence[GeoEntity]):
    for ((dim_type, label), group_tags) in get_physical_group_tags(entities).items():
        physical_group_tag = gmsh.model.addPhysicalGroup(dim_type.value, group_tags)
        gmsh.model.set_physical_name(dim_type.value, physical_group_tag, label)

@dataclass
class PlaneSurface(GeoEntity):
    curve_loops: Sequence[CurveLoop]
    "outline curve loop that make up the surface"

    label: Optional[str] = None
    "label for physical group surface"

    tag: int = -1
    "tag of the surface"

    def __post_init__(self):
        self.type = DimType.SURFACE
        
    def before_sync(self, ctx: GeoContext):
        if not self.is_synced:
            curve_loop_tags = [curve_loop.before_sync(ctx) for curve_loop in self.curve_loops]
            self.tag = self.tag or gmsh.model.occ.add_plane_surface(curve_loop_tags, self.tag)
        return self.tag

    def after_sync(self, ctx: GeoContext):
        for curve_loop in self.curve_loops:
            curve_loop.after_sync(ctx)

        # Assume that the PlaneSurface is the top-level
        if ctx.dimension == 2:
            set_physical_groups(ctx, [*self.get_curves(), self])

    def get_coords(self, num_pnts: int = 20, is_cosine_sampling: bool = False):
        for curve_loop in self.curve_loops:
            yield curve_loop.get_coords(num_pnts, is_cosine_sampling)

    def get_curves(self):
        return [curve for curve_loop in self.curve_loops for curve in curve_loop.curves]
