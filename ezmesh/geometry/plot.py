from typing import Optional, Sequence, Union, cast
from plotly import graph_objects as go
from ezmesh.geometry.curve_loop import CurveLoop
from ezmesh.geometry.edge import Edge
from ezmesh.geometry.transaction import GeoEntityTransaction
from ezmesh.geometry.plane_surface import PlaneSurface
from ezmesh.geometry.point import Point
from ezmesh.geometry.volume import Volume
import numpy.typing as npt
import numpy as np
from ezmesh.utils.types import NumpyFloat

def plot_entities(
    entities: Union[GeoEntityTransaction, Sequence[GeoEntityTransaction]], 
    title: str = "Surface", 
    samples_per_spline: int = 20, 
):
    entities = entities if isinstance(entities, Sequence) else [entities]
    fig = go.Figure(
        layout=go.Layout(title=go.layout.Title(text=title))
    )
    
    # exterior_coords: list[tuple[Optional[str], npt.NDArray[NumpyFloat]]] = []

    surface_coord_groups: dict[str, list[np.ndarray]] = {}
    edge_coord_groups: dict[str, list[np.ndarray]] = {}


    for entity in entities:
        if isinstance(entity, (Volume, PlaneSurface)):
            surfaces = entity.get_surfaces() if isinstance(entity, Volume) else [entity]
            for surface in surfaces:
                surface_label = surface.label or f"Surface{surface.tag}"
                if surface.tag not in surface_coord_groups:
                    surface_coord_groups[surface_label] = []
                
                face_edge_coords: list[np.ndarray] = []
                for edge in surface.get_edges():
                    edge_label = edge.label or f"Edge{edge.tag}"
                    edge_coords = edge.get_coords(samples_per_spline)
                    if edge.tag not in edge_coord_groups:
                        edge_coord_groups[edge_label] = []
                    edge_coord_groups[edge_label].append(edge_coords)
                    face_edge_coords.append(edge_coords)

                surface_coord_groups[surface_label].append(face_edge_coords)
            
        elif isinstance(entity, Edge):
            edge_coords = entity.get_coords(samples_per_spline)
            edge_label = entity.label or f"Edge{entity.tag}"
            edge_coord_groups[edge_label].append(edge_coords)

        else:
            raise ValueError(f"Unknown entity type: {type(entities[0])}")

    scatter_groups: dict[str, list[np.ndarray]] = {}

    surface_num = 0
    for label, surface_coord_group in surface_coord_groups.items():
        for exterior_coords in surface_coord_group:
            for exterior_coord in exterior_coords:
                fig.add_scatter3d(
                    x=exterior_coord[:,0],
                    y=exterior_coord[:,1],
                    z=exterior_coord[:,2],
                    name=label or f"Surface{surface_num}",
                )
            surface_num += 1

    # for label, exterior_coord in exterior_coords:
    #     if not label:
    #         continue
    #     if label not in scatter_groups:
    #         scatter_groups[label] = []
    #     scatter_groups[label].append(exterior_coord)

    # for label, exterior_coord_group in scatter_groups.items():
    #     exterior_coord_group = np.array(exterior_coord_group)
    #     if exterior_coord_group.shape[1] == 2:
    #         fig.add_scatter(
    #             x=exterior_coord_group[:,0],
    #             y=exterior_coord_group[:,1],
    #             name=label,
    #             fill="toself"
    #         )
    #     else:

    #         fig.add_scatter3d(
    #             x=exterior_coord_group[:,0],
    #             y=exterior_coord_group[:,1],
    #             z=exterior_coord_group[:,2],
    #             name=label,
    #             fill="toself"
    #         )


    fig.layout.yaxis.scaleanchor = "x"  # type: ignore
    fig.show()