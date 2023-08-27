import gmsh
from dataclasses import dataclass
from typing import Optional
import numpy as np
from ezmesh.entity import Entity
from ezmesh.transaction import MultiEntityTransaction
from ezmesh.utils.types import OrderedSet



@dataclass(eq=False)
class UnstructuredBoundaryLayer(MultiEntityTransaction):
    "geometric series boundary layer for unstructured meshes"

    entities: OrderedSet[Entity]
    "faces to be added to the boundary layer"

    ratio: float
    "size Ratio Between Two Successive Layers"

    hwall_n: float
    "mesh size normal to the the wall"

    num_layers: int
    "number of layers"

    def before_gen(self):
        heights = [self.hwall_n]
        for i in range(1, self.num_layers): 
            # geometric series for boundary layer heights
            heights.append(heights[-1] + heights[0] * self.ratio**i)
        
        dimTags = [(entity.dim, entity.tag) for entity in self.entities]
        extruded_bnd_layer = gmsh.model.geo.extrudeBoundaryLayer(dimTags, [1] * self.num_layers, heights, True)

        top = []
        for i in range(1, len(extruded_bnd_layer)):
            if extruded_bnd_layer[i][0] == 3:
                top.append(extruded_bnd_layer[i-1])
        gmsh.model.geo.synchronize()
        bnd = gmsh.model.getBoundary(top)
        gmsh.model.geo.addCurveLoop([c[1] for c in bnd])



@dataclass(eq=False)
class UnstructuredBoundaryLayer2D(MultiEntityTransaction):
    "boundary layer for unstructured 2D meshes"

    entities: OrderedSet[Entity]
    "edges to be added to the boundary layer"

    ratio: Optional[float] = None
    "size Ratio Between Two Successive Layers"

    hwall_n: Optional[float] = None
    "mesh size Normal to the The Wal"

    hfar: Optional[float] = None
    "element size far from the wall"

    aniso_max: Optional[float] = None
    "threshold angle for creating a mesh fan in the boundary layer"

    thickness: Optional[float] = None
    "maximal thickness of the boundary layer"

    intersect_metrics: bool = False
    "intersect metrics of all faces"

    is_quad_mesh: bool = False
    "generate recombined elements in the boundary layer"

    def before_gen(self):
        self.tag = gmsh.model.mesh.field.add('BoundaryLayer')
        edge_tags = [edge.tag for edge in self.entities]
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
