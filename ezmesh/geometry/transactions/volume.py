import gmsh
from dataclasses import dataclass
from typing import Optional, Sequence, cast
from ezmesh.geometry.transactions.plane_surface import PlaneSurface, set_physical_groups
from ezmesh.geometry.transactions.edge import Edge
from ezmesh.geometry.transaction import Context, DimType, GeoEntity
from ezmesh.geometry.transactions.surface_loop import SurfaceLoop



@dataclass
class Volume(GeoEntity):
    surface_loops: Sequence[SurfaceLoop]
    "surface loop of volume"

    label: Optional[str] = None
    "label for physical group volume"

    tag: Optional[int] = None
    "tag of entity"

    def __post_init__(self):
        self.type = DimType.VOLUME

    def before_sync(self, ctx: Context):
        surface_loop_tags = [surface_loop.before_sync(ctx) for surface_loop in self.surface_loops]
        self.tag = self.tag or gmsh.model.occ.addVolume(surface_loop_tags)
        return self.tag

    def after_sync(self, ctx: Context):
        for surface_loop in self.surface_loops:
            surface_loop.after_sync(ctx)
        set_physical_groups(ctx, [*self.get_edges(), *self.get_surfaces()])


    def get_edges(self):
        edges: Sequence[Edge] = []
        for surface_loop in self.surface_loops:
            edges += surface_loop.get_edges()
        return edges

    def get_surfaces(self):
        surfaces: Sequence[PlaneSurface] = []
        for surface_loop in self.surface_loops:
            surfaces += surface_loop.surfaces
        return surfaces

    @staticmethod
    def from_tag(tag: int, ctx: Context):
        surface_loops = []
        surface_loop_tags, surface_tags = gmsh.model.occ.get_surface_loops(tag)

        for i, surface_loop_tag in enumerate(surface_loop_tags):
            curve_loop = SurfaceLoop.from_tag(surface_loop_tag, cast(Sequence[int], surface_tags[i]), ctx)
            surface_loops.append(curve_loop)

        return Volume(surface_loops, tag=tag)
