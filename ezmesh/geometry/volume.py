
from dataclasses import dataclass
from typing import Sequence, cast
import gmsh
from ezmesh.geometry.entity import DimType, MeshContext, GeoEntity
from ezmesh.geometry.surface_loop import SurfaceLoop

@dataclass
class Volume(GeoEntity):
    surface_loops: Sequence[SurfaceLoop]
    "surface loop of volume"

    def __post_init__(self):
        super().__init__()
        self.dim_type = DimType.VOLUME

    def before_sync(self, ctx: MeshContext):
        surface_loop_tags = [surface_loop.before_sync(ctx) for surface_loop in self.surface_loops]
        self.tag = gmsh.model.geo.add_volume(surface_loop_tags)
        return self.tag

    def after_sync(self, ctx: MeshContext):
        for surface_loop in self.surface_loops:
            surface_loop.after_sync(ctx)

    @staticmethod
    def from_tag(tag: int):
        surface_loops = []
        surface_loop_tags, surface_tags = gmsh.model.occ.get_surface_loops(tag)

        for i, surface_loop_tag in enumerate(surface_loop_tags):
            curve_loop = SurfaceLoop.from_tag(surface_loop_tag, cast(Sequence[int], surface_tags[i]))
            surface_loops.append(curve_loop)

        volume = Volume(surface_loops)
        volume.tag = tag

        return volume