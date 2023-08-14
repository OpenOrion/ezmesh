import gmsh
from dataclasses import dataclass, field
from typing import Optional, Sequence, Union, cast
from ezmesh.transactions.transaction import GeoContext, Transaction
from ezmesh.geometry.transactions.curve import Curve
from ezmesh.geometry.geometry import PlaneSurface
from ezmesh.geometry.transactions.point import Point
from ezmesh.geometry.transactions.volume import Volume

@dataclass
class BoundaryLayer(Transaction):
    targets: Sequence[Union[Curve, PlaneSurface]]
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
        
    def before_sync(self, ctx: GeoContext):
        if self.tag is None:
            heights = [self.hwall_n]
            for i in range(1, self.num_layers): 
                heights.append(heights[-1] + heights[0] * self.ratio**i)
            
            dimTags = [(target.type.value, target.tag) for target in self.targets]
            extruded_bnd_layer = gmsh.model.occ.extrudeBoundaryLayer(dimTags, [1] * self.num_layers, heights, True)

            top = []
            for i in range(1, len(extruded_bnd_layer)):
                if extruded_bnd_layer[i][0] == 3:
                    top.append(extruded_bnd_layer[i-1])
            gmsh.model.occ.synchronize()
            bnd = gmsh.model.getBoundary(top)
            self.tag = gmsh.model.occ.addCurveLoop([c[1] for c in bnd])

    def after_sync(self, ctx: GeoContext):
        ...


@dataclass
class BoundaryLayer2D(Transaction):
    curves: Sequence[Curve]
    "curves to be added to the boundary layer"

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

    def before_sync(self, ctx: GeoContext):
        super().before_sync(ctx)

    def after_sync(self, ctx: GeoContext):
        if not self.tag:
            self.tag = gmsh.model.mesh.field.add('BoundaryLayer')
            curve_tags = [curve.tag for curve in self.curves]
            gmsh.model.mesh.field.setNumbers(self.tag, 'CurvesList', curve_tags)
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
class TransfiniteCurveField(Transaction):
    curves: Sequence[Curve]
    "curves to be added to the boundary layer"

    node_counts: Sequence[int]
    "number per curve"

    mesh_types: Optional[Sequence[str]] = None
    "mesh type for each curve"

    coefs: Optional[Sequence[float]] = None
    "coefficients for each curve"

    def __post_init__(self):
        self.is_run = False

    def before_sync(self, ctx: GeoContext):
        super().before_sync(ctx)

    def after_sync(self, ctx: GeoContext):
        if not self.is_run:
            for i, curve in enumerate(self.curves):
                gmsh.model.mesh.setTransfiniteCurve(
                    curve.tag,
                    numNodes=self.node_counts[i]+1,
                    # meshType=get_property(self.mesh_types, i, curve.label, "Progression"),
                    # coef=get_property(self.coefs, i, curve.label, 1.0)
                )

            self.is_run = True


@dataclass
class TransfiniteSurfaceField(Transaction):
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

    def before_sync(self, ctx: GeoContext):
        super().before_sync(ctx)

    def after_sync(self, ctx: GeoContext):      
        if not self.is_run:
            corner_tags = [cast(int, corner.tag) for corner in self.corners]
            for surface in cast(Sequence[PlaneSurface], self.surfaces):
                gmsh.model.mesh.setTransfiniteSurface(surface.tag, self.arrangement, corner_tags)

@dataclass
class TransfiniteVolumeField(Transaction):
    """
    A plane surface with transfinite meshing. Normal plane if corners are not defined.
    """
    volumes: Union[Volume, Sequence[Volume]]
    "surface to apply field"

    def __post_init__(self):
        self.is_run = False
        self.volumes = [self.volumes] if isinstance(self.volumes, Volume) else self.volumes

    def before_sync(self, ctx: GeoContext):
        super().before_sync(ctx)

    def after_sync(self, ctx: GeoContext):      
        if not self.is_run:
            for volume in cast(Sequence[Volume], self.volumes):
                gmsh.model.mesh.setTransfiniteVolume(volume.tag)