
from .mesh import ElementType, Mesh
from typing import Any, Dict, List
import numpy.typing as npt
import numpy as np
import gmsh

def import_from_su2(file_path: str):
    """Import a mesh from SU2 format"""
    from su2fmt import parse_mesh
    su2_mesh = parse_mesh(file_path)
    meshes = []
    for zone in su2_mesh.zones:
        element_types = []
        for su2_element_type in zone.element_types:
            element_type = ElementType[su2_element_type.name]
            element_types.append(element_type)
        mesh = Mesh(
            zone.ndime,
            zone.elements,
            element_types,
            zone.points,
            zone.markers,
        )
        meshes.append(mesh)
    if len(meshes) == 1:
        return meshes[0]
    return meshes

def import_from_msh(file_path: str):
    """Import a mesh from Gmsh format"""
    import gmsh
    gmsh.initialize()
    gmsh.open(file_path)
    model = gmsh.model
    mesh = import_from_gmsh()
    gmsh.finalize()
    return mesh

def import_from_file(file_path: str):
    """Import a mesh from a file"""
    if file_path.endswith('.su2'):
        return import_from_su2(file_path)
    elif file_path.endswith('.msh'):
        return import_from_msh(file_path)
    raise ValueError(f"File extension not supported: {file_path}")

def import_from_gmsh() -> Mesh:
    dim = gmsh.model.getDimension()
    elements: List[npt.NDArray[np.uint16]] = []
    element_types: List[ElementType] = []

    node_tags, points_concatted, _ = gmsh.model.mesh.getNodes()
    node_indices = np.argsort(node_tags-1) # type: ignore
    points = np.array(points_concatted, dtype=np.float64).reshape((-1, 3))[node_indices]

    
    grouped_concatted_elements = gmsh.model.mesh.getElements()
    for element_type_value, grouped_element_tags, grouped_node_tags_concatted in zip(*grouped_concatted_elements):        
        if element_type_value == ElementType.POINT.value or element_type_value == ElementType.LINE.value:
            continue
        num_nodes = gmsh.model.mesh.getElementProperties(element_type_value)[3]
        group_elements = np.array(grouped_node_tags_concatted, dtype=np.uint16).reshape((-1, num_nodes)) - 1
        elements += list(group_elements)
        element_types += [ElementType(element_type_value)] * len(elements)

    # get physical groups
    markers: Dict[str, List[npt.NDArray[np.uint16]]] = {}
    physical_groups = gmsh.model.getPhysicalGroups()
    for group_dim, group_tag in physical_groups:
        marker_name = gmsh.model.getPhysicalName(group_dim, group_tag)
        if marker_name not in markers:
            markers[marker_name] = []
        entities = gmsh.model.getEntitiesForPhysicalGroup(group_dim, group_tag)
        for entity in entities:
            marker_grouped_concatted_elements = gmsh.model.mesh.getElements(group_dim, tag=entity)
            assert len(marker_grouped_concatted_elements[0]) == 1, "There should only be one group"
            marker_element_type, marker_node_tags_concatted = marker_grouped_concatted_elements[0][0], marker_grouped_concatted_elements[2][0]
            assert marker_element_type == ElementType.LINE.value, "All elements in a group must be a line"
            marker_elements = np.array(marker_node_tags_concatted, dtype=np.uint16).reshape((-1, 2)) - 1
            
            markers[marker_name] += list(marker_elements)

    return Mesh(
        dim,
        elements,
        element_types,
        points,
        markers,
    )
