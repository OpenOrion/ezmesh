import gmsh
from dataclasses import dataclass
from typing import Optional, Sequence, cast
from ezmesh.geometry.transaction import GeoContext, DimType, GeoEntity
from ezmesh.geometry.transactions.curve_loop import CurveLoop

def get_physical_group_tags(entities: Sequence[GeoEntity]):
    physical_groups: dict[tuple[DimType, str], list[int]] = {}
    for entity in entities:
        if not entity.label or entity.tag == -1 or entity.is_commited:
            continue
        if (entity.type, entity.label) not in physical_groups:
            physical_groups[(entity.type, entity.label)] = []
        physical_groups[(entity.type, entity.label)].append(entity.tag)
    return physical_groups

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
        super().__init__(DimType.SURFACE)

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
            set_physical_groups(ctx, [*self.curves, self])


    @property
    def curves(self):
        return [curve for curve_loop in self.curve_loops for curve in curve_loop.curves]
