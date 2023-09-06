import gmsh
from dataclasses import dataclass
from typing import Optional
import numpy as np
from ezmesh.entity import ENTITY_DIM_MAPPING, Entity
from ezmesh.transaction import MultiEntityTransaction
from ezmesh.utils.types import OrderedSet

def get_boundary_sizes(ratio: float, size: float, num_layers: int):
    sizes = [size]
    for i in range(1, num_layers): 
        # geometric series for boundary layer heights
        sizes.append(sizes[-1] + sizes[0] * ratio**i)
    return sizes

def get_boundary_num_layers(length: float, ratio: float, normal_height: Optional[float] = None, num_layers: Optional[int] = None):
    if num_layers is None:
        assert normal_height is not None, "hwall_n must be specified if num_layers is not specified"
        return np.log((normal_height + length*ratio - length)/normal_height)/np.log(ratio)
    else:
        return num_layers


@dataclass(eq=False)
class UnstructuredBoundaryLayer(MultiEntityTransaction):
    "geometric series boundary layer for unstructured meshes"

    entities: OrderedSet[Entity]
    "faces to be added to the boundary layer"

    ratio: float
    "size Ratio Between Two Successive Layers"

    size: float
    "mesh size normal to the the wall"

    num_layers: int
    "number of layers"

    def before_gen(self):
        sizes = get_boundary_sizes(self.ratio, self.size, self.num_layers)
        
        dim_tags = []
        for face in self.entities:
            assert face.dim == ENTITY_DIM_MAPPING["face"], "boundary layer can only be applied to faces"
            dim_tags.append((face.dim, face.tag))

        extruded_bnd_layer = gmsh.model.geo.extrudeBoundaryLayer(dim_tags, [1] * self.num_layers, sizes, True)

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

    ratio: float
    "size Ratio Between Two Successive Layers"

    size: float
    "mesh size Normal to the wall"

    num_layers: int
    "number of layers"

    def before_gen(self):
        edge_tags = []
        for edge in self.entities:
            assert edge.dim == ENTITY_DIM_MAPPING["edge"], "boundary layer can only be applied to edges"
            edge_tags.append(edge.tag)
        sizes = get_boundary_sizes(self.ratio, self.size, self.num_layers)


        self.tag = gmsh.model.mesh.field.add('BoundaryLayer')
        # gmsh.model.mesh.field.setNumber(self.tag, "Size", sizes[0])
        # gmsh.model.mesh.field.setNumber(self.tag, "SizeFar", sizes[-1])
        # gmsh.model.mesh.field.setNumber(self.tag, "Thickness", sizes[-1])
        # gmsh.model.mesh.field.setNumbers(self.tag, "SizesList", sizes)
        gmsh.model.mesh.field.setNumbers(self.tag, 'CurvesList', edge_tags)
        gmsh.model.mesh.field.setNumber(self.tag, "Quads", 1)
        gmsh.model.mesh.field.setAsBoundaryLayer(self.tag)
