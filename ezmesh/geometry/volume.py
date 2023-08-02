
from dataclasses import dataclass
from typing import Optional, Sequence, cast
import gmsh
from ezmesh.utils.types import DimType
from ezmesh.geometry.edge import Edge
from ezmesh.geometry.entity import MeshContext, GeoEntity
from ezmesh.geometry.surface_loop import SurfaceLoop

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

    def before_sync(self, ctx: MeshContext):
        surface_loop_tags = [surface_loop.before_sync(ctx) for surface_loop in self.surface_loops]
        self.tag = self.tag or gmsh.model.geo.add_volume(surface_loop_tags)
        return self.tag

    def after_sync(self, ctx: MeshContext):
        for surface_loop in self.surface_loops:
            surface_loop.after_sync(ctx)
        
        for (label, edge_tags) in ctx.get_edge_physical_groups().items():
            physical_group_tag = gmsh.model.addPhysicalGroup(DimType.CURVE.value, edge_tags)
            gmsh.model.set_physical_name(DimType.CURVE.value, physical_group_tag, label)

    def get_edges(self):
        edges: Sequence[Edge] = []
        for surface_loop in self.surface_loops:
            edges += surface_loop.get_edges()
        return edges

    @staticmethod
    def from_tag(tag: int, ctx: MeshContext):
        surface_loops = []
        surface_loop_tags, surface_tags = gmsh.model.occ.get_surface_loops(tag)

        for i, surface_loop_tag in enumerate(surface_loop_tags):
            curve_loop = SurfaceLoop.from_tag(surface_loop_tag, cast(Sequence[int], surface_tags[i]), ctx)
            surface_loops.append(curve_loop)

        return Volume(surface_loops, tag=tag)
