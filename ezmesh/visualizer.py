from typing import List, Union
from ezmesh.mesh import Mesh
from .utils import generate_color_legend_html, generate_rgb_values, to_rgb_str
import pythreejs
from IPython.display import display
from IPython.core.display import HTML
import ipywidgets as widgets
import numpy as np



def visualize_mesh(meshes: Union[Mesh, List[Mesh]], view_width=800, view_height=600):
    coord_html = widgets.HTML("Coords: ()")
    def on_surf_mousemove(change):
        # write coordinates to html container
        if change.new is None:
            coord_html.value = "Coords: ()"
        else:
            coord_html.value = "Coords: (%f, %f, %f)" % change.owner.point

    if not isinstance(meshes, list):
        meshes = [meshes]

    # Legend Colors
    mesh_colors = generate_rgb_values(len(meshes), is_grayscale=True)
    marker_colors = generate_rgb_values(sum([len(mesh.groups) for mesh in meshes]))

    # Legend Color Labels
    marker_color_labels = {}
    mesh_color_labels = {}

    mesh_line_segements = []
    mesh_meshes = []
    for i, mesh in enumerate(meshes):
        mesh_color = mesh_colors[i]
        mesh_color_labels[f"Zone {i}"] = mesh_color

        # Marker line segment points and colors
        marker_line_points = []
        marker_segment_colors = []

        # Non-marker line segment points
        non_marker_line_points = []
        group_elements_to_tag = {}
        for group_name, group_elements in mesh.groups.items():
            for elements in group_elements:
                group_elements_to_tag[(elements[0], elements[1])] = group_name
        
        for point_tags in mesh.elements:
            for i in range(len(point_tags)):
                if i + 1 < len(point_tags):
                    line_point_inds = (point_tags[i+1], point_tags[i])
                else:
                    line_point_inds = (point_tags[0], point_tags[i])
                line_points = [mesh.node_points[line_point_inds[0]].tolist(), mesh.node_points[line_point_inds[1]].tolist()]

                

                marker_point_inds = line_point_inds if line_point_inds in group_elements_to_tag else line_point_inds[::-1]
                if marker_point_inds in group_elements_to_tag:
                    marker_name = group_elements_to_tag[marker_point_inds]
                    if marker_name not in marker_color_labels:
                        marker_color_labels[marker_name] = marker_colors[len(marker_color_labels)]
                    marker_color = marker_color_labels[marker_name]
                    marker_segment_colors.append([marker_color, marker_color])
                    marker_line_points.append(line_points)
                else:
                    non_marker_line_points.append(line_points)

        non_marker_lines = pythreejs.LineSegments2(
            pythreejs.LineSegmentsGeometry(positions=non_marker_line_points),
            pythreejs.LineMaterial(linewidth=1, color=to_rgb_str(mesh_color))
        )
        mesh_line_segements.append(non_marker_lines)

        if len(marker_line_points) > 0:
            marker_lines = pythreejs.LineSegments2(
                pythreejs.LineSegmentsGeometry(positions=marker_line_points, colors=marker_segment_colors),
                pythreejs.LineMaterial(linewidth=2, vertexColors='VertexColors')
            )
            mesh_line_segements.append(marker_lines)


        mesh_mesh_geom = pythreejs.BufferGeometry(attributes=dict(
            position=pythreejs.BufferAttribute(mesh.node_points, normalized=False),
            index=pythreejs.BufferAttribute(np.concatenate(mesh.elements), normalized=False),
        ))

        mesh_mesh = pythreejs.Mesh(
            geometry=mesh_mesh_geom,
            material=pythreejs.MeshLambertMaterial(color='white', side='DoubleSide'),
        )
        mesh_meshes.append(mesh_mesh)


    camera = pythreejs.PerspectiveCamera(position=[0, 0, 1], far=1000, near=0.001, aspect=view_width/view_height)
    scene = pythreejs.Scene(children=mesh_line_segements+mesh_meshes, background="black")

    orbit_controls = pythreejs.OrbitControls(controlling=camera)
    
    pickable_objects = pythreejs.Group()
    for mesh_mesh in mesh_meshes:
        pickable_objects.add(mesh_mesh)

    mousemove_picker = pythreejs.Picker(
        controlling = pickable_objects,
        event = 'mousemove'
    )
    mousemove_picker.observe(on_surf_mousemove, names=['faceIndex'])

    renderer = pythreejs.Renderer(
        camera=camera,
        scene=scene,
        controls=[orbit_controls, mousemove_picker],
        width=view_width,
        height=view_height
    )

    # Plot renderer
    display(coord_html, renderer)
    
    # Plot legend
    marker_legend_html = generate_color_legend_html("Markers", marker_color_labels)
    mesh_legend_html = generate_color_legend_html("Zones", mesh_color_labels)
    display(HTML(marker_legend_html+mesh_legend_html))
