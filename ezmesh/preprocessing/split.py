import numpy as np
import cadquery as cq
from cadquery.cq import VectorLike, CQObject
from typing import Literal, Optional, Sequence, Union, cast
from ezmesh.utils.cq import CQExtensions, CQLinq
from ezmesh.utils.types import LineTuple, VectorTuple, Number
from jupyter_cadquery.cadquery import show


def scale(obj: CQObject, x: float = 1, y: float = 1, z: float = 1):
    t = cq.Matrix([
        [x, 0, 0, 0],
        [0, y, 0, 0],
        [0, 0, z, 0],
        [0, 0, 0, 1]
    ])
    return obj.transformGeometry(t)

Axis = Union[Literal["X", "Y", "Z"], VectorTuple, cq.Vector]
def get_normal_from_axis(axis: Axis):
    if isinstance(axis, str):
        return cq.Vector([1 if axis == "X" else 0, 1 if axis == "Y" else 0, 1 if axis == "Z" else 0])        
    elif isinstance(axis, tuple):
        return cq.Vector(axis)
    return axis

class Split:
    @staticmethod
    def from_plane(
        base_pnt: VectorLike = (0,0,0), 
        angle: VectorTuple = (0,0,0), 
    ):
        return cq.Face.makePlane(None, None, base_pnt, tuple(np.radians(angle)))

    @staticmethod
    def from_faces(
        workplane: cq.Workplane, 
        face_type: Literal['interior', 'exterior'],
        snap_tolerance: Optional[float] = None,
    ):
        type_groups = CQLinq.groupByTypes(workplane, only_faces=True)
        dir = "away" if face_type == "interior" else "towards"
        face_edge_groups: dict[cq.Edge, set[cq.Face]] = {}

        for face in type_groups[face_type]:
            assert isinstance(face, cq.Face)
            edges = CQLinq.select(face, "edge")
            for edge in edges:
                if edge not in face_edge_groups:
                    face_edge_groups[edge] = set()
                face_edge_groups[edge].add(face)

        for edge, faces in face_edge_groups.items():
            average_normal = cq.Vector(tuple(np.average([face.normalAt().toTuple() for face in faces], axis=0)))
            edge_vec = cq.Vector(edge.endPoint().toTuple()) - cq.Vector(edge.startPoint().toTuple())
            is_parallel = edge_vec.dot(average_normal) == 0
            if is_parallel:
                yield Split.from_edge(workplane, edge, average_normal, dir, snap_tolerance)



    @staticmethod
    def from_anchor(
        workplane: cq.Workplane, 
        anchor: Union[list[VectorTuple], VectorTuple] = (0,0,0), 
        dir: Union[list[VectorTuple], VectorTuple] = (0,0,0),
        snap_tolerance: Optional[float] = None,
        until: Literal["next", "all"] = "next"
    ):
        anchors = [anchor] if isinstance(anchor, tuple) else anchor
        dirs = [dir] if isinstance(dir, tuple) else dir
        assert len(anchors) == len(dirs), "anchors and dirs must be the same length"

        edges = []
        for anchor, dir in zip(anchors, dirs):
            split_face = Split.from_plane(workplane, anchor, dir)
            if until == "next":
                intersect_vertex = CQExtensions.split_intersect(workplane, anchor, split_face, snap_tolerance)
                edges.append((anchor, intersect_vertex.toTuple())) # type: ignore
            else:
                edges.append(split_face)
        return Split.from_lines(workplane, edges)
    
    @staticmethod
    def from_pnts(workplane: cq.Workplane, pnts: Sequence[cq.Vector]):
        return cq.Face.makeFromWires(cq.Wire.makePolygon(pnts))

    @staticmethod
    def from_edge(
        workplane: cq.Workplane,
        edge: cq.Edge, 
        axis: Union[Literal["X", "Y", "Z"], VectorTuple, cq.Vector] = "Z",
        dir: Literal["away", "towards", "both"] = "both",
        snap_tolerance: Optional[float] = None
    ):
        scaled_edge: cq.Edge = scale(edge, z=10)
        maxDim = workplane.findSolid().BoundingBox().DiagonalLength * 10.0
        normal_vector = get_normal_from_axis(axis)        

        max_dim_edge = scaled_edge.translate(normal_vector * maxDim) if dir in ("both", "towards") else scaled_edge
        min_dim_edge = scaled_edge.translate(-normal_vector * maxDim) if dir in ("both", "away") else scaled_edge
        
        split_face = cq.Face.makeFromWires(cq.Wire.assembleEdges([
            min_dim_edge,
            cq.Edge.makeLine(min_dim_edge.endPoint(), max_dim_edge.endPoint()),
            max_dim_edge,
            cq.Edge.makeLine(max_dim_edge.startPoint(), min_dim_edge.startPoint()),
        ]))

        if snap_tolerance:
            intersect_vertex = CQExtensions.split_intersect(workplane, edge.startPoint(), split_face, snap_tolerance)
            intersect_vec = cq.Vector(intersect_vertex.toTuple()) - cq.Vector(edge.startPoint().toTuple())
            intersect_vec_norm = intersect_vec/intersect_vec.Length
            # print(intersect_vec_norm.toTuple(), edge.startPoint().toTuple())
            return Split.from_edge(workplane, edge, intersect_vec_norm, "towards")
        # show(workplane.newObject([min_dim_edge, max_dim_edge]))
        # print(min_dim_edge.startPoint().toTuple())
        # print(min_dim_edge.endPoint().toTuple())
        # print(max_dim_edge.startPoint().toTuple())
        # print(max_dim_edge.endPoint().toTuple())
        # print(min_dim_edge.startPoint().toTuple())

        return split_face

    @staticmethod
    def from_lines(
        workplane: cq.Workplane, 
        lines: Union[list[LineTuple], LineTuple], 
        axis: Union[Literal["X", "Y", "Z"], VectorTuple] = "Z",
        dir: Literal["away", "towards", "both"] = "both",
    ):
        
        edges_pnts = np.array([lines, lines] if isinstance(lines, tuple) else lines)
        maxDim = workplane.findSolid().BoundingBox().DiagonalLength * 10.0
        normal_vector = np.array(get_normal_from_axis(axis).toTuple())

        if dir in ("both", "towards"):
            edges_pnts[0] += maxDim * normal_vector
        if dir in ("both", "away"):        
            edges_pnts[-1] -= maxDim * normal_vector

        side1 = edges_pnts[:, 0].tolist()
        side2 = edges_pnts[:, 1].tolist()
        wire_pnts = [side1[0], *side2, *side1[1:][::-1]] 
        return Split.from_pnts(workplane, wire_pnts)

def split_workplane(workplane: cq.Workplane, splits: Sequence[cq.Face]):
    for split in splits:      
        workplane = workplane.split(split)
    return workplane


# from OCP.BRepAlgoAPI import BRepAlgoAPI_Splitter
# from OCP.TopTools import TopTools_ListOfShape

# def split_workplane(workplane: cq.Workplane, splits: Sequence[cq.Face]):
#     shape_list = TopTools_ListOfShape()
#     for shape in workplane.vals():
#         shape_list.Append(shape.wrapped)


#     # Define the splitting plane
#     tool_list = TopTools_ListOfShape()
#     for split_tool in splits:
#         tool_list.Append(split_tool.wrapped)

#     # Create the splitter algorithm
#     splitter = BRepAlgoAPI_Splitter()

#     # Set the shape to be split and the splitting tool (plane face)
#     splitter.SetArguments(shape_list)
#     splitter.SetTools(tool_list)

#     # Perform the splitting operation
#     splitter.Build()
    
#     compound = cq.Compound(cq.Compound._makeCompound([splitter.Shape()]))
#     return workplane.newObject([compound])
