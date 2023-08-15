import gmsh
from dataclasses import dataclass
from typing import Optional, Sequence
from ezmesh.transactions.transaction import Entity, Transaction

@dataclass
class BoundaryLayer(Transaction):
    faces: Sequence[Entity]
    "faces to be added to the boundary layer"

    num_layers: int
    "number of layers"

    hwall_n: float
    "mesh size normal to the the wall"

    ratio: float
    "size Ratio Between Two Successive Layers"

    is_quad_mesh: bool = True
    "generate recombined elements in the boundary layer"

    def before_gen(self):
        heights = [self.hwall_n]
        for i in range(1, self.num_layers): 
            heights.append(heights[-1] + heights[0] * self.ratio**i)
        
        dimTags = [(entity.dim_type.value, entity.tag) for entity in self.faces]
        extruded_bnd_layer = gmsh.model.geo.extrudeBoundaryLayer(dimTags, [1] * self.num_layers, heights, True)

        top = []
        for i in range(1, len(extruded_bnd_layer)):
            if extruded_bnd_layer[i][0] == 3:
                top.append(extruded_bnd_layer[i-1])
        gmsh.model.geo.synchronize()
        bnd = gmsh.model.getBoundary(top)
        gmsh.model.geo.addCurveLoop([c[1] for c in bnd])


@dataclass
class BoundaryLayer2D(Transaction):
    curves: Sequence[Entity]
    "target to be added to the boundary layer"

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

    def before_gen(self):
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