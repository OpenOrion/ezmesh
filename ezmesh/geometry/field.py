import gmsh
from dataclasses import dataclass, field
from typing import Optional, Sequence, Union, cast
from ezmesh.geometry.entity import MeshContext, GeoTransaction
from ezmesh.geometry.point import Point
from ezmesh.utils.geometry import PropertyType, get_property
from ezmesh.utils.types import Number
from typing import Protocol


class Field(Protocol):
    def after_sync(self, ctx: MeshContext, entity: GeoTransaction):
        "completes transaction after syncronization and returns tag."
        ...

@dataclass
class BoundaryLayerField(Field):
    aniso_max: Optional[float] = None
    "threshold angle for creating a mesh fan in the boundary layer"

    hfar: Optional[float] = None
    "element size far from the wall"

    hwall_n: Optional[float] = None
    "mesh Size Normal to the The Wal"

    ratio: Optional[float] = None
    "size Ratio Between Two Successive Layers"

    thickness: Optional[float] = None
    "maximal thickness of the boundary layer"

    intersect_metrics: bool = False
    "intersect metrics of all surfaces"

    is_quad_mesh: bool = False
    "generate recombined elements in the boundary layer"

    def __post_init__(self):
        self.tags = set()

    def after_sync(self, ctx: MeshContext, curve_loop: GeoTransaction):
        from ezmesh.geometry.curve_loop import CurveLoop
        assert isinstance(curve_loop, CurveLoop) and curve_loop.tag is not None
        
        if curve_loop.tag not in self.tags:
            tag = gmsh.model.mesh.field.add('BoundaryLayer')
            edge_tags = [edge.tag for edge in curve_loop.edges]
            gmsh.model.mesh.field.setNumbers(tag, 'CurvesList', edge_tags)
            if self.aniso_max:
                gmsh.model.mesh.field.setNumber(tag, "AnisoMax", self.aniso_max)
            if self.intersect_metrics:
                gmsh.model.mesh.field.setNumber(tag, "IntersectMetrics", self.intersect_metrics)
            if self.is_quad_mesh:
                gmsh.model.mesh.field.setNumber(tag, "Quads", int(self.is_quad_mesh))
            if self.hfar:
                gmsh.model.mesh.field.setNumber(tag, "hfar", self.hfar)
            if self.hwall_n:
                gmsh.model.mesh.field.setNumber(tag, "hwall_n", self.hwall_n)
            if self.ratio:
                gmsh.model.mesh.field.setNumber(tag, "ratio", self.ratio)
            if self.thickness:
                gmsh.model.mesh.field.setNumber(tag, "thickness", self.thickness)

            gmsh.model.mesh.field.setAsBoundaryLayer(tag)
            self.tags.add(curve_loop.tag)

@dataclass
class TransfiniteCurveField(Field):
    node_counts: PropertyType[int]
    "number per curve"

    mesh_types: Optional[PropertyType[str]] = None
    "mesh type for each curve"

    coefs: Optional[PropertyType[float]] = None
    "coefficients for each curve"

    def __post_init__(self):
        self.tags = set()

    def after_sync(self, ctx: MeshContext, curve_loop: GeoTransaction):
        from ezmesh.geometry.curve_loop import CurveLoop
        assert isinstance(curve_loop, CurveLoop) and curve_loop.tag is not None

        if curve_loop.tag not in self.tags:
            for i, edge in enumerate(curve_loop.edges):
                gmsh.model.mesh.set_transfinite_curve(
                    edge.tag,
                    numNodes=cast(Number, get_property(self.node_counts, i, edge.label))+1,
                    meshType=get_property(self.mesh_types, i, edge.label, "Progression"),
                    coef=get_property(self.coefs, i, edge.label, 1.0)
                )
            self.tags.add(curve_loop.tag)

@dataclass
class TransfiniteSurfaceField(Field):
    """
    A plane surface with transfinite meshing. Normal plane if corners are not defined.
    """
    corners: Optional[Union[tuple[str,str], list[Point]]] = None
    "corners of transfinite surface"

    arrangement: str = "Left"
    "arrangement of transfinite surface"


    def __post_init__(self):
        self.tags = set()

    def after_sync(self, ctx: MeshContext, surface: GeoTransaction):
        from ezmesh.geometry.plane_surface import PlaneSurface
        assert isinstance(surface, PlaneSurface) and surface.tag is not None
        
        if self.corners is not None and surface.tag not in self.tags:
            if isinstance(self.corners, tuple):
                first_corner_group, second_corner_group = self.corners
                primary_curve_loop = surface.curve_loops[0]
                corner_tags = [
                    primary_curve_loop.edge_groups[first_corner_group][0].start.tag, 
                    primary_curve_loop.edge_groups[first_corner_group][-1].end.tag,
                    primary_curve_loop.edge_groups[second_corner_group][0].start.tag, 
                    primary_curve_loop.edge_groups[second_corner_group][-1].end.tag
                ]
            else:
                corner_tags = [cast(int, corner.tag) for corner in self.corners]
            gmsh.model.mesh.set_transfinite_surface(surface.tag, self.arrangement, corner_tags)
            self.tags.add(surface.tag)

        super().after_sync(ctx, surface)

