import numpy as np
import cadquery as cq
from cadquery.cq import VectorLike
from typing import Literal, Optional, Sequence, Union, cast
from ezmesh.utils.cq import CQExtensions, CQLinq
from ezmesh.utils.types import LineTuple, VectorTuple, Number
from jupyter_cadquery.cadquery import show


Axis = Union[Literal["X", "Y", "Z"], VectorTuple]
def get_normal_from_axis(axis: Axis):
    if isinstance(axis, str):
        return np.array([1 if axis == "X" else 0, 1 if axis == "Y" else 0, 1 if axis == "Z" else 0])        
    else:
        return np.array(axis)

class Split:
    @staticmethod
    def from_plane(
        workplane: cq.Workplane,
        base_pnt: VectorLike = (0,0,0), 
        dir: VectorTuple = (0,0,0), 

    ):
        return cq.Face.makePlane(None, None, base_pnt, tuple(np.radians(dir)))

    @staticmethod
    def from_faces(workplane: cq.Workplane, face_type: Literal['interior', 'exterior']):
        type_groups = CQLinq.groupByTypes(workplane, only_faces=True)
        # edges = CQLinq.select(type_groups[face_type], "edge")
        for face in type_groups[face_type]:
            assert isinstance(face, cq.Face)
            edges = CQLinq.select(face, "edge")

            face_normal = face.normalAt()
            edge_vec = cq.Vector()
            for edge in edges:
                edge_vertices = edge.Vertices()
                edge_vec = cq.Vector(edge_vertices[-1].toTuple()) - cq.Vector(edge_vertices[0].toTuple())
                if not face_normal.cross(edge_vec).Length < 0.5:
                    edge_tuple = tuple([vertex.toTuple() for vertex in edge.Vertices()])
                    yield Split.from_lines(workplane, edge_tuple, face.normalAt(edge.Center()).toTuple(), "away")

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
    def from_edges(workplane: cq.Workplane, edges: Sequence[cq.Edge]):
        wire = cq.Wire.assembleEdges(edges)
        return cq.Face.makeFromWires(wire)

    @staticmethod
    def from_lines(
        workplane: cq.Workplane, 
        lines: Union[list[LineTuple], LineTuple], 
        axis: Union[Literal["X", "Y", "Z"], VectorTuple] = "Z",
        dir: Literal["away", "towards", "both"] = "both",
        maxDimAxis: Optional[Union[Literal["X", "Y", "Z"], VectorTuple]] = "Z",
    ):
        edges_pnts = np.array([lines, lines] if isinstance(lines, tuple) else lines)
        maxDim = workplane.findSolid().BoundingBox().DiagonalLength * 10.0
        normal_vector = get_normal_from_axis(axis)

        if dir in ("both", "towards"):
            edges_pnts[0] += maxDim * normal_vector
        if dir in ("both", "away"):        
            edges_pnts[-1] -= maxDim * normal_vector

        if maxDimAxis and maxDimAxis != axis:
            max_dim_normal = get_normal_from_axis(maxDimAxis)
            edges_pnts[0][0] += maxDim * max_dim_normal
            edges_pnts[-1][0] += maxDim * max_dim_normal

            edges_pnts[0][-1] -= maxDim * max_dim_normal
            edges_pnts[-1][-1] -= maxDim * max_dim_normal

        side1 = edges_pnts[:, 0].tolist()
        side2 = edges_pnts[:, 1].tolist()
        wire_pnts = [side1[0], *side2, *side1[1:][::-1]] 
        return Split.from_pnts(workplane, wire_pnts)


def split_workplane(workplane: cq.Workplane, splits: Sequence[cq.Face]):
    for split in splits:      
        workplane = workplane.split(split)
    return workplane