import gmsh
from dataclasses import dataclass, field
from typing import Optional, Sequence, cast
from ezmesh.geometry.entity import DimType, MeshContext, GeoEntity
from ezmesh.geometry.curve_loop import CurveLoop
from ezmesh.geometry.edge import Edge
from ezmesh.geometry.fields.field import Field

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

    def before_sync(self, ctx: MeshContext):
        curve_loop_tags = [curve_loop.before_sync(ctx) for curve_loop in self.curve_loops]
        self.tag = self.tag or gmsh.model.geo.add_plane_surface(curve_loop_tags)
        return self.tag

    def after_sync(self, ctx: MeshContext):
        edge_groups:  dict[str, list[Edge]] = {}
        for curve_loop in self.curve_loops:
            curve_loop.after_sync(ctx)
            edge_groups = {**edge_groups, **curve_loop.edge_groups}
        
        for (name, edges) in edge_groups.items():
            segment_tags = [segment.tag for segment in edges if segment.tag is not None]
            physical_group_tag = gmsh.model.add_physical_group(DimType.CURVE.value, segment_tags)
            gmsh.model.set_physical_name(DimType.CURVE.value, physical_group_tag, name)

        # NOTICE: add physical group for surface regardless of label because SU2 output bug
        physical_group_tag = gmsh.model.add_physical_group(DimType.SURFACE.value, [self.tag])
        if self.label is not None:
            gmsh.model.set_physical_name(DimType.SURFACE.value, physical_group_tag, self.label)

        if self.is_quad_mesh:
            gmsh.model.mesh.set_recombine(DimType.SURFACE.value, self.tag)

        for field in self.fields:
            field.after_sync(ctx, self)


    @staticmethod
    def from_tag(tag: int):
        curve_loop_tags, curve_tags = gmsh.model.occ.get_curve_loops(tag)
        curve_loops = [ 
            CurveLoop.from_tag(curve_loop_tag, cast(Sequence[int], curve_tags[i]))
            for i, curve_loop_tag in enumerate(curve_loop_tags)
        ]
        surface = PlaneSurface(curve_loops, tag=tag)
        return surface