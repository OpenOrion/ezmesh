import gmsh
from dataclasses import dataclass
from typing import Optional, Sequence, cast
from ezmesh.geometry.transaction import Context, DimType, GeoEntity
from ezmesh.geometry.transactions.curve_loop import CurveLoop
from ezmesh.geometry.transactions.edge import Edge

def set_physical_groups(ctx: Context):
    for (label, edges) in ctx.get_label_groups(DimType.CURVE).items():
        if (DimType.CURVE.value, label) not in ctx.physical_groups:
            edge_tags = [edge.tag for edge in edges]
            physical_group_tag = gmsh.model.addPhysicalGroup(DimType.CURVE.value, edge_tags)
            gmsh.model.set_physical_name(DimType.CURVE.value, physical_group_tag, label)

    for (label, surfaces) in ctx.get_label_groups(DimType.SURFACE).items():
        if (DimType.SURFACE.value, label) not in ctx.physical_groups:
            surface_tags = [edge.tag for edge in surfaces]
            physical_group_tag = gmsh.model.addPhysicalGroup(DimType.SURFACE.value, surface_tags)
            gmsh.model.set_physical_name(DimType.SURFACE.value, physical_group_tag, label)



@dataclass
class PlaneSurface(GeoEntity):
    curve_loops: Sequence[CurveLoop]
    "outline curve loop that make up the surface"

    label: Optional[str] = None
    "label for physical group surface"

    tag: Optional[int] = None
    "tag of the surface"

    def __post_init__(self):
        self.type = DimType.SURFACE

    def before_sync(self, ctx: Context):
        curve_loop_tags = [curve_loop.before_sync(ctx) for curve_loop in self.curve_loops]
        self.tag = self.tag or gmsh.model.geo.add_plane_surface(curve_loop_tags)
        ctx.add_surface(self)
        return self.tag

    def after_sync(self, ctx: Context):
        for curve_loop in self.curve_loops:
            curve_loop.after_sync(ctx)

        # Assume that the PlaneSurface is the top-level
        if ctx.dimension == 2:
            set_physical_groups(ctx)

    def get_coords(self, num_pnts: int = 20, is_cosine_sampling: bool = False):
        for curve_loop in self.curve_loops:
            yield curve_loop.get_coords(num_pnts, is_cosine_sampling)


    def get_edges(self):
        return [edge for curve_loop in self.curve_loops for edge in curve_loop.edges]

    @staticmethod
    def from_tag(tag: int, ctx: Context):
        curve_loop_tags, curve_tags = gmsh.model.occ.get_curve_loops(tag)
        curve_loops = [ 
            CurveLoop.from_tag(curve_loop_tag, cast(Sequence[int], curve_tags[i]), ctx)
            for i, curve_loop_tag in enumerate(curve_loop_tags)
        ]
        return PlaneSurface(curve_loops, tag=tag)
