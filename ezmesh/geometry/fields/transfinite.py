import gmsh
from dataclasses import dataclass
from typing import Optional, cast
from ezmesh.geometry.fields.field import Field
from ezmesh.geometry.entity import DimType, MeshContext, GeoEntity
from ezmesh.geometry.point import Point
from ezmesh.utils.geometry import PropertyType, get_property
from ezmesh.utils.types import Number

@dataclass
class TransfiniteCurveField(Field):
    node_counts: PropertyType[int]
    "number per curve"

    mesh_types: Optional[PropertyType[str]] = None
    "mesh type for each curve"

    coefs: Optional[PropertyType[float]] = None
    "coefficients for each curve"

    def __post_init__(self):
        super().__init__()
        self.dim_type = DimType.CURVE

    def after_sync(self, ctx: MeshContext, curve_loop: GeoEntity):
        from ezmesh.geometry.curve_loop import CurveLoop
        assert isinstance(curve_loop, CurveLoop)
        for i, edge in enumerate(curve_loop.edges):
            gmsh.model.mesh.set_transfinite_curve(
                edge.tag,
                numNodes=cast(Number, get_property(self.node_counts, i, edge.label))+1,
                meshType=get_property(self.mesh_types, i, edge.label, "Progression"),
                coef=get_property(self.coefs, i, edge.label, 1.0)
            )
        super().after_sync(ctx, curve_loop)


@dataclass
class TransfiniteSurfaceField(Field):
    """
    A plane surface with transfinite meshing. Normal plane if corners are not defined.
    """
    corners: Optional[list[Point]] = None
    "corners of transfinite surface"

    arrangement: str = "Left"
    "arrangement of transfinite surface"

    def after_sync(self, ctx: MeshContext, surface: GeoEntity):
        from ezmesh.geometry.plane_surface import PlaneSurface
        assert isinstance(surface, PlaneSurface)

        if self.corners is not None:
            corner_tags = [cast(int, corner.tag) for corner in self.corners]
            gmsh.model.mesh.set_transfinite_surface(surface.tag, self.arrangement, corner_tags)

        super().after_sync(ctx, surface)

