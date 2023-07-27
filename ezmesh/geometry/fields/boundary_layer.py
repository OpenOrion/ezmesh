import gmsh
from dataclasses import dataclass
from typing import Optional
from ezmesh.geometry.fields.field import Field
from ezmesh.geometry.entity import MeshContext, GeoEntity

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


    def after_sync(self, ctx: MeshContext, curve_loop: GeoEntity):
        from ezmesh.geometry.curve_loop import CurveLoop
        assert isinstance(curve_loop, CurveLoop)

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
