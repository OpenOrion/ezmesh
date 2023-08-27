from dataclasses import dataclass
from plotly import graph_objects as go
import cadquery as cq
from cadquery.cq import CQObject, VectorLike
from typing import Iterable, Literal, Optional, Sequence, Union, cast
import numpy as np
from ezmesh.utils.plot import add_plot
from ezmesh.utils.shapes import get_sampling
from ezmesh.utils.types import OrderedSet, NumpyFloat

CQType = Literal["compound", "solid", "shell", "face", "wire", "edge", "vertex"]
CQGroupTypeString = Literal["split", "interior", "exterior"]
CQEdgeOrFace = Union[cq.Edge, cq.Face]

@dataclass
class DirectedPath:
    edge: cq.Edge
    "edge or face of path"

    direction: int = 1
    "direction of path"

    def __post_init__(self):
        assert isinstance(self.edge, cq.Edge), "edge must be an edge"
        assert self.direction in [-1, 1], "direction must be -1 or 1"
        self.vertices = self.edge.Vertices()[::self.direction]
        self.start = self.vertices[0]
        self.end = self.vertices[-1]



        
CQ_TYPE_STR_MAPPING: dict[type[CQObject], CQType] = {
    cq.Compound: "compound",
    cq.Solid: "solid",
    cq.Shell: "shell",
    cq.Face: "face",
    cq.Wire: "wire",
    cq.Edge: "edge",
    cq.Vertex: "vertex",
}

class CQLinq:    
    @staticmethod
    def select_tagged(workplane: cq.Workplane, tags: Union[str, Iterable[str]], type: CQType):
        for tag in ([tags] if isinstance(tags, str) else tags):
            yield from CQLinq.select(workplane._getTagged(tag).vals(), type)    

    @staticmethod
    def select(target: Union[cq.Workplane, Iterable[CQObject], CQObject], type: CQType):
        cq_objs = target.vals() if isinstance(target, cq.Workplane) else (target if isinstance(target, Iterable) else [target])
        for occ_obj in cq_objs:
            assert isinstance(occ_obj, cq.Shape), "target must be a shape"
            if type == "compound":
                yield from occ_obj.Compounds()
            if type == "solid":
                yield from occ_obj.Solids()
            elif type == "shell":
                yield from occ_obj.Shells()
            elif type == "face":
                yield from occ_obj.Faces()
            elif type == "wire":
                yield from occ_obj.Wires()
            elif type == "edge":
                yield from occ_obj.Edges()
            elif type == "vertex":
                yield from occ_obj.Vertices()

    @staticmethod
    def select_batch(target: Union[cq.Workplane, Iterable[CQObject]], parent_type: CQType, child_type: CQType):
        cq_objs = list(target.vals() if isinstance(target, cq.Workplane) else target)
        if CQ_TYPE_STR_MAPPING[type(cq_objs[0])] == child_type:
            yield cq_objs
        else:
            parent_cq_objs = CQLinq.select(cq_objs, parent_type)
            for parent_occ_obj in parent_cq_objs:
                yield CQLinq.select([parent_occ_obj], child_type)

    @staticmethod
    def filter(objs: Iterable[CQObject], filter_objs: Iterable[CQObject], invert: bool):
        filter_objs = set(filter_objs)
        for occ_obj in objs:
            if (invert and occ_obj in filter_objs) or (not invert and occ_obj not in filter_objs):
                yield occ_obj

    @staticmethod
    def sort(target: Union[cq.Edge, Sequence[cq.Edge]]):
        objs = [target] if isinstance(target, cq.Edge) else target

        unsorted_cq_edges = cast(Sequence[cq.Edge], list(CQLinq.select(objs, "edge")))
        cq_edges = list(unsorted_cq_edges[1:])
        sorted_paths = [DirectedPath(unsorted_cq_edges[0])]
        while cq_edges:
            for i, cq_edge in enumerate(cq_edges):
                vertices = cq_edge.Vertices()
                if vertices[0].toTuple() == sorted_paths[-1].end.toTuple():
                    sorted_paths.append(DirectedPath(cq_edge))
                    cq_edges.pop(i)
                    break
                elif vertices[-1].toTuple() == sorted_paths[-1].end.toTuple():
                    sorted_paths.append(DirectedPath(cq_edge, direction=-1))
                    cq_edges.pop(i)
                    break
                elif vertices[0].toTuple() == sorted_paths[0].start.toTuple():
                    sorted_paths.insert(0, DirectedPath(cq_edge, direction=-1))
                    cq_edges.pop(i)
                    break
            else:
                raise ValueError("Edges do not form a closed loop")
        
        assert sorted_paths[-1].end == sorted_paths[0].start, "Edges do not form a closed loop"
        return sorted_paths
    

    @staticmethod
    def groupByTypes(target: Union[cq.Workplane, Sequence[CQObject]]): 
        workplane = target if isinstance(target, cq.Workplane) else cq.Workplane().add(target)
        add_wire_to_group = lambda wires, group: group.update([
            *wires,
            *CQLinq.select(wires, "edge"),
            *CQLinq.select(wires, "vertex"),
        ])
        
        groups: dict[CQGroupTypeString, OrderedSet[CQObject]] = {
            "split": OrderedSet[CQObject](),
            "interior": OrderedSet[CQObject](),
            "exterior": OrderedSet[CQObject](),
        }
        faces = list(CQLinq.select(target, "face"))
        if len(faces) > 0:
            for face in faces:
                assert isinstance(face, cq.Face), "object must be a face"
                split_intersect = CQExtensions.split_intersect(workplane, face.Center(), cq.Edge.makeLine(face.Center(), face.Center() + (face.normalAt()*1E-5)))
                is_interior = CQExtensions.is_interior_face(face) 

                if split_intersect:
                    face_registry = groups["split"]
                else:
                    face_registry = groups["interior" if is_interior else "exterior"]
                face_registry.add(face)
                add_wire_to_group(face.Wires(), face_registry)
        else:
            first_face = cast(cq.Face, faces[0])
            add_wire_to_group(first_face.innerWires(), groups["interior"])
            add_wire_to_group([first_face.outerWire()], groups["exterior"])

        return groups

    @staticmethod
    def groupByAngles(cq_edges: Sequence[cq.Edge], angle_threshold: float):
        # cq_faces = list(CQLinq.select(target, "face"))
        # for cq_face in cq_faces:
        # cq_edges = cast(list[cq.Edge], CQLinq.select(face, "edge"))

        sorted_paths = CQLinq.sort(cq_edges)

        # 1) gather sorted angles of edges
        # 2) shuffle to next group in case in the middle of current group
        angles = []
        prev_path = sorted_paths[-1]
        shuffle_num, shuffle_cutoff = 0, False
        for path in sorted_paths: # type: ignore
            angle = CQExtensions.get_angle_between(prev_path.edge, path.edge)
            
            if shuffle_cutoff:
                if angle > np.radians(angle_threshold):
                    shuffle_cutoff = True
                shuffle_num += 1

            angles.append(angle)
            prev_path = path

        # arrange groups based on angles
        groups: list[list[DirectedPath]] = []
        for i, angle in enumerate(angles[shuffle_num:] + angles[:shuffle_num]):
            path = sorted_paths[i+shuffle_num]
            if angle >= np.radians(angle_threshold):
                groups.append([])
            groups[-1].append(path)
        return groups


class CQExtensions:
    @staticmethod
    def is_interior_face(face: CQObject, invert: bool = False):
        assert isinstance(face, cq.Face), "object must be a face"
        face_normal = face.normalAt()
        face_centroid = face.Center()
        interior_dot_product = face_normal.dot(face_centroid)
        return (not invert and interior_dot_product < 0) or (invert and interior_dot_product >= 0)

    @staticmethod
    def find_nearest_point(workplane: cq.Workplane, near_point: cq.Vertex, tolerance: float = 1e-2):
        min_dist_vertex, min_dist = None, float("inf")
        for vertex in workplane.vertices().vals():
            dist = cast(cq.Vertex, vertex).distance(near_point)
            if dist < min_dist and dist <= tolerance:
                min_dist_vertex, min_dist = vertex, dist
        return min_dist_vertex

    @staticmethod
    def split_intersect(workplane: cq.Workplane, anchor: VectorLike, splitter: CQObject, snap_tolerance: Optional[float] = None):
        intersected_vertices = workplane.intersect(cq.Workplane(splitter)).vertices().vals()
        min_dist_vertex, min_dist = None, float("inf") 
        for vertex in intersected_vertices:
            try:
                to_intersect_line = cq.Edge.makeLine(anchor, vertex.toTuple()) # type: ignore
                intersect_dist = to_intersect_line.Length() # type: ignore
                if intersect_dist < min_dist:
                    min_dist_vertex, min_dist = vertex, intersect_dist
            except: ...
        if snap_tolerance and isinstance(min_dist_vertex, cq.Vertex):
            nearest_point = CQExtensions.find_nearest_point(workplane, min_dist_vertex, snap_tolerance)
            if nearest_point:
                return nearest_point
        return min_dist_vertex

    @staticmethod
    def get_angle_between(prev: CQEdgeOrFace, curr: CQEdgeOrFace):
        if isinstance(prev, cq.Edge) and isinstance(curr, cq.Edge):
            prev_tangent_vec = prev.tangentAt(0.5) # type: ignore
            tangent_vec = curr.tangentAt(0.5)      # type: ignore
        else:
            prev_tangent_vec = prev.normalAt() # type: ignore
            tangent_vec = curr.normalAt()      # type: ignore
        angle = np.arccos(prev_tangent_vec.dot(tangent_vec)/(prev_tangent_vec.Length * tangent_vec.Length))
        assert not np.isnan(angle), "angle should not be NaN"
        return angle


    @staticmethod
    def plot_workplane(
        target: Union[cq.Workplane, Iterable[CQObject], Iterable[Iterable[CQObject]]], 
        edge_group_names: Optional[Sequence[str]] = None,
        title: str = "Plot", 
        samples_per_spline: int = 50,
    ):
        fig = go.Figure(
            layout=go.Layout(title=go.layout.Title(text=title))
        )

        if isinstance(target, cq.Workplane):
            edge_groups = [CQLinq.select(target, "edge")]
        elif isinstance(target, Iterable):
            edge_groups = [target]
        else:
            edge_groups = target

        for i, edges in enumerate(edge_groups):
            for edge in edges:
                edge_name = edge_group_names[i] if edge_group_names else f"Edge{i}"
                sampling = get_sampling(0, 1, samples_per_spline, False)
                coords = np.array([vec.toTuple() for vec in edge.positions(sampling)], dtype=NumpyFloat) # type: ignore
                add_plot(coords, fig, edge_name)

        fig.layout.yaxis.scaleanchor = "x"  # type: ignore
        fig.show()

    @staticmethod
    def import_workplane(target: Union[cq.Workplane, str, Iterable[CQObject]]):
        if isinstance(target, str):
            if target.lower().endswith(".step"):
                workplane = cq.importers.importStep(target)
            elif target.lower().endswith(".dxf"):
                workplane = cq.importers.importDXF(target)
            else:
                raise ValueError(f"Unsupported file type: {target}")
        elif isinstance(target, Iterable):
            workplane = cq.Workplane().newObject(target)
        else:
            workplane = target
        if isinstance(workplane.val(), cq.Wire):
            workplane = cq.Workplane().newObject(workplane.extrude(-1).faces(">Z").vals())

        workplane.tag("root")

        return workplane


    @staticmethod
    def get_selector(selector: Union[cq.Selector, str, None], group: Optional[OrderedSet[CQObject]], indices: Optional[Sequence[int]] = None):
        selectors = []
        if isinstance(selector, str):
            selector = selectors.append(cq.StringSyntaxSelector(selector))
        elif isinstance(selector, cq.Selector):
            selectors.append(selector)

        if group is not None:
            selectors.append(GroupSelector(group))
        if indices is not None:
            selectors.append(IndexSelector(indices))

        if len(selectors) > 0:
            prev_selector = selectors[0]
            for selector in selectors[1:]:
                prev_selector = cq.selectors.AndSelector(prev_selector, selector)
            return prev_selector


class IndexSelector(cq.Selector):
    def __init__(self, indices: Sequence[int]):
        self.indices = indices
    def filter(self, objectList):
        return [objectList[i] for i in self.indices]

class GroupSelector(cq.Selector):
    def __init__(self, allow: OrderedSet[CQObject], is_interior: bool = True):
        self.allow = allow
        self.is_interior = is_interior
    def filter(self, objectList):
        filtered_objs = []
        for obj in objectList:
            if obj in self.allow:
                filtered_objs.append(obj)
        return filtered_objs
