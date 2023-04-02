from typing import Any, List, Union, cast
from .mesh import Mesh
from .utils.visualization import generate_color_legend_html, generate_rgb_values, to_rgb_str
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
    marker_colors = generate_rgb_values(sum([len(mesh.markers) for mesh in meshes]))

    # Legend Color Labels
    marker_color_labels = {}
    mesh_color_labels = {}

    marker_line_segments = []
    buffer_meshes = []
    target_point_spheres = []
    for i, mesh in enumerate(meshes):
        mesh_color = mesh_colors[i]
        mesh_color_labels[f"Zone {i}"] = mesh_color

        # Marker line segment points and colors
        marker_line_points = []
        marker_segment_colors = []
        marker_elements_to_name = {}
        for marker_name, marker_elements in mesh.markers.items():
            for elements in marker_elements:
                marker_elements_to_name[(elements[0], elements[1])] = marker_name

        # Non-marker line segment points
        non_marker_line_points = []

        for target_point_tag in mesh.target_points.values():
            target_point_sphere = pythreejs.Mesh(
                geometry=pythreejs.SphereGeometry(radius=0.05),
                material=pythreejs.MeshLambertMaterial(color='red', side='DoubleSide'),
            )
            target_point_sphere.position = mesh.points[target_point_tag].tolist()
            target_point_spheres.append(target_point_sphere)

        for point_tags in mesh.elements:
            for i in range(len(point_tags)):
                if i + 1 < len(point_tags):
                    line_point_tags = (point_tags[i+1], point_tags[i])
                else:
                    line_point_tags = (point_tags[0], point_tags[i])
                line_points = [mesh.points[line_point_tags[0]].tolist(), mesh.points[line_point_tags[1]].tolist()]

                marker_point_tags = line_point_tags if line_point_tags in marker_elements_to_name else line_point_tags[::-1]
                if marker_point_tags in marker_elements_to_name:
                    marker_name = marker_elements_to_name[marker_point_tags]
                    if marker_name not in marker_color_labels:
                        marker_color_labels[marker_name] = marker_colors[len(marker_color_labels)]
                    marker_color = marker_color_labels[marker_name]
                    marker_segment_colors.append([marker_color, marker_color])
                    marker_line_points.append(line_points)
                else:
                    non_marker_line_points.append(line_points)

        non_marker_lines = pythreejs.LineSegments2(
            cast(Any, pythreejs.LineSegmentsGeometry(positions=non_marker_line_points)),
            cast(Any, pythreejs.LineMaterial(linewidth=1, color=to_rgb_str(mesh_color)))
        )
        marker_line_segments.append(non_marker_lines)

        if len(marker_line_points) > 0:
            marker_lines = pythreejs.LineSegments2(
                cast(Any, pythreejs.LineSegmentsGeometry(positions=marker_line_points, colors=marker_segment_colors)),
                cast(Any, pythreejs.LineMaterial(linewidth=2, vertexColors='VertexColors'))
            )
            marker_line_segments.append(marker_lines)

        buffer_geom = pythreejs.BufferGeometry(attributes=dict(
            position=pythreejs.BufferAttribute(mesh.points, normalized=False),
            index=pythreejs.BufferAttribute(np.concatenate(mesh.elements), normalized=False),
        ))

        buffer_mesh = pythreejs.Mesh(
            geometry=buffer_geom,
            material=pythreejs.MeshLambertMaterial(color='white', side='DoubleSide'),
        )
        buffer_meshes.append(buffer_mesh)

    camera = pythreejs.PerspectiveCamera(position=[0, 0, 1], far=1000, near=0.001, aspect=cast(Any, view_width/view_height))
    scene = pythreejs.Scene(children=[*marker_line_segments, *buffer_meshes, *target_point_spheres, pythreejs.AmbientLight(intensity=0.8)], background="black")
    orbit_controls = pythreejs.OrbitControls(controlling=camera)

    pickable_objects = pythreejs.Group()
    for buffer_mesh in buffer_meshes:
        pickable_objects.add(buffer_mesh)

    mousemove_picker = pythreejs.Picker(
        controlling=pickable_objects,
        event='mousemove'
    )
    mousemove_picker.observe(on_surf_mousemove, names=cast(Any, ['faceIndex']))

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
