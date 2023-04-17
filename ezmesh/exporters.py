from typing import List, Union
from .mesh import Mesh


def export_to_su2(meshes: Union[Mesh, List[Mesh]], file_path: str):
    """Export a mesh from SU2 format"""
    from su2fmt import Mesh as Su2Mesh, export_mesh
    from su2fmt.mesh import ElementType as Su2ElementType, Zone
    if not isinstance(meshes, list):
        meshes = [meshes]
    zones = []
    for izone, mesh in enumerate(meshes):
        element_types: List[Su2ElementType] = []
        for element_type in mesh.element_types:
            try:
                su2_element_type = Su2ElementType[element_type.name]
                element_types.append(su2_element_type)
            except:
                print("Warning: Element type not supported: ", element_type.name)
        zone = Zone(
            izone=izone+1,
            ndime=mesh.dim,
            elements=mesh.elements,
            element_types=element_types,
            points=mesh.points,
            markers=mesh.markers,
        )
        zones.append(zone)
    su2_mesh = Su2Mesh(len(zones), zones)
    return export_mesh(su2_mesh, file_path)