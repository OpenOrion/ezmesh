import gmsh
from dataclasses import dataclass
from typing import Optional, Sequence
from ezmesh.geometry.transaction import DimType, GeoEntity, Context
from ezmesh.geometry.transactions.plane_surface import PlaneSurface

@dataclass
class SurfaceLoop(GeoEntity):
    surfaces: Sequence[PlaneSurface]
    "Lines of curve"

    label: Optional[str] = None
    "label for physical group surface loop"

    tag: Optional[int] = None
    "tag of surface loop"

    def __post_init__(self):
        self.type = DimType.SURFACE

    def before_sync(self, ctx: Context):
        surface_loop_tags = [surface.before_sync(ctx) for surface in self.surfaces]
        self.tag = self.tag or gmsh.model.geo.addSurfaceLoop(surface_loop_tags)
        return self.tag

    def after_sync(self, ctx: Context):
        for surface in self.surfaces:
            surface.after_sync(ctx)

    def get_edges(self):
        return [edge for surface in self.surfaces for edge in surface.get_edges()]

    @staticmethod
    def from_tag(tag: int, surface_tags: Sequence[int], ctx: Context):
        surfaces = [PlaneSurface.from_tag(surface_tag, ctx) for surface_tag in surface_tags]
        return SurfaceLoop(surfaces, tag=tag)
