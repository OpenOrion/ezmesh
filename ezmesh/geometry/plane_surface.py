import gmsh
from dataclasses import dataclass, field
from typing import Optional, Sequence, cast
from ezmesh.utils.types import DimType
from ezmesh.geometry.entity import MeshContext, GeoEntity
from ezmesh.geometry.curve_loop import CurveLoop
from ezmesh.geometry.edge import Edge
from ezmesh.geometry.field import Field

@dataclass
class PlaneSurface(GeoEntity):
    curve_loops: Sequence[CurveLoop]
    "outline curve loop that make up the surface"

    label: Optional[str] = None
    "label for physical group surface"

    is_quad_mesh: bool = False
    "if true, surface mesh is made of quadralateral cells, else triangular cells"

    fields: Sequence[Field] = field(default_factory=list)
    "fields to be added to the surface"

    tag: Optional[int] = None
    "tag of the surface"

    def __post_init__(self):
        self.type = DimType.SURFACE

    def before_sync(self, ctx: MeshContext):
        curve_loop_tags = [curve_loop.before_sync(ctx) for curve_loop in self.curve_loops]
        self.tag = self.tag or gmsh.model.geo.add_plane_surface(curve_loop_tags)
        return self.tag

    def after_sync(self, ctx: MeshContext):
        for curve_loop in self.curve_loops:
            curve_loop.after_sync(ctx)

        # NOTICE: add physical group for surface regardless of label because SU2 output bug
        physical_group_tag = gmsh.model.add_physical_group(DimType.SURFACE.value, [self.tag])
        if self.label is not None:
            gmsh.model.set_physical_name(DimType.SURFACE.value, physical_group_tag, self.label)

        if self.is_quad_mesh:
            gmsh.model.mesh.set_recombine(DimType.SURFACE.value, self.tag)

        # Assume that the PlaneSurface is the top-level
        if ctx.dimension == 2:
            for (label, edge_tags) in ctx.get_edge_physical_groups().items():
                physical_group_tag = gmsh.model.addPhysicalGroup(DimType.CURVE.value, edge_tags)
                gmsh.model.set_physical_name(DimType.CURVE.value, physical_group_tag, label)


        for field in self.fields:
            field.after_sync(ctx, self)

    def get_edges(self):
        edges: Sequence[Edge] = []
        for curve_loop in self.curve_loops:
            edges += curve_loop.edges
        return edges


    @staticmethod
    def from_tag(tag: int, ctx: MeshContext):
        curve_loop_tags, curve_tags = gmsh.model.occ.get_curve_loops(tag)
        curve_loops = [ 
            CurveLoop.from_tag(curve_loop_tag, cast(Sequence[int], curve_tags[i]), ctx)
            for i, curve_loop_tag in enumerate(curve_loop_tags)
        ]
        return PlaneSurface(curve_loops, tag=tag)
