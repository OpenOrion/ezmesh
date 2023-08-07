import gmsh
from dataclasses import dataclass, field
from typing import Optional, Sequence, Union, cast
from ezmesh.geometry.curve_loop import CurveLoop
from ezmesh.geometry.edge import Edge
from ezmesh.geometry.transaction import MeshContext, GeoTransaction
from ezmesh.geometry.plane_surface import PlaneSurface
from ezmesh.geometry.point import Point
from ezmesh.geometry.volume import Volume
from ezmesh.utils.geometry import PropertyType, get_property
from ezmesh.utils.types import Number

@dataclass
class ExtrudedBoundaryLayer(GeoTransaction):
    targets: Sequence[Union[Edge, PlaneSurface]]
    "target to be added to the boundary layer"

    num_layers: int
    "number of layers"

    hwall_n: float
    "mesh size normal to the the wall"

    ratio: float
    "size Ratio Between Two Successive Layers"

    is_quad_mesh: bool = True
    "generate recombined elements in the boundary layer"

    def __post_init__(self):
        self.tag = None
        
    def before_sync(self, ctx: MeshContext):
        if self.tag is None:
            heights = [self.hwall_n]
            for i in range(1, self.num_layers): 
                heights.append(heights[-1] + heights[0] * self.ratio**i)
            
            dimTags = [(target.type.value, target.tag) for target in self.targets]
            extruded_bnd_layer = gmsh.model.geo.extrudeBoundaryLayer(dimTags, [1] * self.num_layers, heights, True)

            top = []
            for i in range(1, len(extruded_bnd_layer)):
                if extruded_bnd_layer[i][0] == 3:
                    top.append(extruded_bnd_layer[i-1])
            gmsh.model.geo.synchronize()
            bnd = gmsh.model.getBoundary(top)
            self.tag = gmsh.model.geo.addCurveLoop([c[1] for c in bnd])

    def after_sync(self, ctx: MeshContext):
        ...


@dataclass
class BoundaryLayerField(GeoTransaction):
    edges: Sequence[Edge]
    "edges to be added to the boundary layer"

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
        self.tag = None

    def before_sync(self, ctx: MeshContext):
        super().before_sync(ctx)

    def after_sync(self, ctx: MeshContext):
        if not self.tag:
            self.tag = gmsh.model.mesh.field.add('BoundaryLayer')
            edge_tags = [edge.tag for edge in self.edges]
            gmsh.model.mesh.field.setNumbers(self.tag, 'CurvesList', edge_tags)
            if self.aniso_max:
                gmsh.model.mesh.field.setNumber(self.tag, "AnisoMax", self.aniso_max)
            if self.intersect_metrics:
                gmsh.model.mesh.field.setNumber(self.tag, "IntersectMetrics", self.intersect_metrics)
            if self.is_quad_mesh:
                gmsh.model.mesh.field.setNumber(self.tag, "Quads", int(self.is_quad_mesh))
            if self.hfar:
                gmsh.model.mesh.field.setNumber(self.tag, "hfar", self.hfar)
            if self.hwall_n:
                gmsh.model.mesh.field.setNumber(self.tag, "hwall_n", self.hwall_n)
            if self.ratio:
                gmsh.model.mesh.field.setNumber(self.tag, "ratio", self.ratio)
            if self.thickness:
                gmsh.model.mesh.field.setNumber(self.tag, "thickness", self.thickness)

            gmsh.model.mesh.field.setAsBoundaryLayer(self.tag)


@dataclass
class TransfiniteCurveField(GeoTransaction):
    edges: Sequence[Edge]
    "edges to be added to the boundary layer"

    node_counts: PropertyType[int]
    "number per curve"

    mesh_types: Optional[PropertyType[str]] = None
    "mesh type for each curve"

    coefs: Optional[PropertyType[float]] = None
    "coefficients for each curve"

    def __post_init__(self):
        self.is_run = False

    def before_sync(self, ctx: MeshContext):
        super().before_sync(ctx)

    def after_sync(self, ctx: MeshContext):
        if not self.is_run:
            for i, edge in enumerate(self.edges):
                gmsh.model.mesh.setTransfiniteCurve(
                    edge.tag,
                    numNodes=cast(Number, get_property(self.node_counts, i, edge.label))+1,
                    # meshType=get_property(self.mesh_types, i, edge.label, "Progression"),
                    # coef=get_property(self.coefs, i, edge.label, 1.0)
                )

            self.is_run = True


@dataclass
class TransfiniteSurfaceField(GeoTransaction):
    """
    A plane surface with transfinite meshing. Normal plane if corners are not defined.
    """
    surfaces: Union[PlaneSurface, Sequence[PlaneSurface]]
    "surface to apply field"

    corners: list[Point] = field(default_factory=list)
    "corners of transfinite surface"

    arrangement: str = "Left"
    "arrangement of transfinite surface"

    def __post_init__(self):
        self.surfaces = [self.surfaces] if isinstance(self.surfaces, PlaneSurface) else self.surfaces
        self.is_run = False

    def before_sync(self, ctx: MeshContext):
        super().before_sync(ctx)

    def after_sync(self, ctx: MeshContext):      
        if not self.is_run:
            corner_tags = [cast(int, corner.tag) for corner in self.corners]
            for surface in cast(Sequence[PlaneSurface], self.surfaces):
                gmsh.model.mesh.setTransfiniteSurface(surface.tag, self.arrangement, corner_tags)

    # @staticmethod
    # def from_labels(surface: PlaneSurface, labels: tuple[str,str], curve_loop: Optional[CurveLoop] = None, arrangement: str = "Left"):
    #     "create transfinite surface from edges"
        
    #     # use primary curve loop of surface if curve loop is not defined
    #     if curve_loop is None:
    #         curve_loop = surface.curve_loops[0]

    #     first_corner_group, second_corner_group = labels
    #     corners = [
    #         curve_loop.edge_groups[first_corner_group][0].start, 
    #         curve_loop.edge_groups[first_corner_group][-1].end,
    #         curve_loop.edge_groups[second_corner_group][0].start, 
    #         curve_loop.edge_groups[second_corner_group][-1].end
    #     ]

    #     return TransfiniteSurfaceField(surface, corners, arrangement)

@dataclass
class TransfiniteVolumeField(GeoTransaction):
    """
    A plane surface with transfinite meshing. Normal plane if corners are not defined.
    """
    volumes: Union[Volume, Sequence[Volume]]
    "surface to apply field"

    def __post_init__(self):
        self.is_run = False
        self.volumes = [self.volumes] if isinstance(self.volumes, Volume) else self.volumes

    def before_sync(self, ctx: MeshContext):
        super().before_sync(ctx)

    def after_sync(self, ctx: MeshContext):      
        if not self.is_run:
            for volume in cast(Sequence[Volume], self.volumes):
                gmsh.model.mesh.setTransfiniteVolume(volume.tag)