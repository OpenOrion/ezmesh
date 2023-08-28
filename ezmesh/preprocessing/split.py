import numpy as np
import cadquery as cq
from typing import Literal, Optional, Sequence, Union
from ezmesh.utils.cq import CQExtensions
from ezmesh.utils.types import EdgeTuple, VectorTuple


class Split:
    @staticmethod
    def from_plane(
        workplane: cq.Workplane,
        base_pnt: VectorTuple = (0,0,0), 
        angle: VectorTuple = (0,0,0), 
    ):
        return cq.Face.makePlane(None, None, tuple(base_pnt), tuple(np.radians(angle)))

    @staticmethod
    def from_anchor(
        workplane: cq.Workplane, 
        anchor: Union[list[VectorTuple], VectorTuple] = (0,0,0), 
        angle: Union[list[VectorTuple], VectorTuple] = (0,0,0),
        snap_tolerance: Optional[float] = None
    ):
        anchors = [anchor] if isinstance(anchor, tuple) else anchor
        angles = [angle] if isinstance(angle, tuple) else angle
        assert len(anchors) == len(angles), "anchors and angles must be the same length"

        edges = []
        for anchor, angle in zip(anchors, angles):
            split_face = Split.from_plane(workplane, anchor, angle)
            intersect_vertex = CQExtensions.split_intersect(workplane, anchor, split_face, snap_tolerance)
            workplane.newObject
            edges.append((anchor, intersect_vertex.toTuple())) # type: ignore
        return Split.from_edges(workplane, edges)
    
    @staticmethod
    def from_pnts(workplane: cq.Workplane, pnts: Sequence[tuple[float, float, float]]):
        return cq.Face.makeFromWires(cq.Wire.makePolygon(pnts))

    @staticmethod
    def from_edges(
        workplane: cq.Workplane, 
        edges: Union[list[EdgeTuple], EdgeTuple], 
        dir: Literal["X", "Y", "Z"] = "Z"
    ):
        edges_pnts = np.array([edges] if isinstance(edges, tuple) else edges)
        maxDim = workplane.findSolid().BoundingBox().DiagonalLength * 10.0


        if len(edges_pnts) == 1:
            top_pnts = edges_pnts[0]
            bottom_pnts = np.array(top_pnts)
        else:
            top_pnts = edges_pnts[:,0]
            bottom_pnts = edges_pnts[:,1]

        top_pnts[:, {"X": 0, "Y": 1, "Z": 2}[dir]] = maxDim
        bottom_pnts[:, {"X": 0, "Y": 1, "Z": 2}[dir]] = -maxDim

        return Split.from_pnts(workplane, [*top_pnts.tolist(), *bottom_pnts[::-1].tolist()])


def split_workplane(workplane: cq.Workplane, splits: Sequence[cq.Face]):
    for split in splits:      
        workplane = workplane.split(split)
    return workplane