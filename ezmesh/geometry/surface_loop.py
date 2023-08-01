import gmsh
from dataclasses import dataclass
from typing import Optional, Sequence
from ezmesh.geometry.entity import MeshContext, GeoTransaction
from ezmesh.geometry.plane_surface import PlaneSurface

@dataclass
class SurfaceLoop(GeoTransaction):
    surfaces: Sequence[PlaneSurface]
    "Lines of curve"

    tag: Optional[int] = None
    "tag of surface loop"

    def before_sync(self, ctx: MeshContext):
        surface_loop_tags = [surface.before_sync(ctx) for surface in self.surfaces]
        self.tag = self.tag or gmsh.model.geo.add_surface_loop(surface_loop_tags)
        return self.tag

    def after_sync(self, ctx: MeshContext):
        for surface in self.surfaces:
            surface.after_sync(ctx)

    def get_edges(self):
        edges = []
        for surface in self.surfaces:
            edges += surface.get_edges()
        return edges

    @staticmethod
    def from_tag(tag: int, surface_tags: Sequence[int], ctx: MeshContext):
        surfaces = [PlaneSurface.from_tag(surface_tag, ctx) for surface_tag in surface_tags]
        return SurfaceLoop(surfaces, tag=tag)
