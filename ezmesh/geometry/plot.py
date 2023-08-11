from typing import Sequence, Union
from plotly import graph_objects as go
from ezmesh.geometry.transactions.edge import Edge
from ezmesh.geometry.transaction import GeoEntity
from ezmesh.geometry.transactions.plane_surface import PlaneSurface
from ezmesh.geometry.transactions.volume import Volume
import numpy.typing as npt
import numpy as np
from ezmesh.utils.types import NumpyFloat


def add_plot(coords: npt.NDArray[NumpyFloat], fig: go.Figure=go.Figure(), label: str="Plot"):
    dim = 3 if np.all(coords[:,2]) else 2
    if dim == 3:
        fig.add_scatter3d(
            x=coords[:,0],
            y=coords[:,1],
            z=coords[:,2],
            name=label,
            mode="lines"                
        )
    else:
        fig.add_scatter(
            x=coords[:,0],
            y=coords[:,1],
            name=label,
            fill="toself",
            mode="lines"
        )

    return fig

def plot_entities(
    entities: Union[GeoEntity, Sequence[GeoEntity]], 
    title: str = "Plot", 
    samples_per_spline: int = 50, 
):
    entities = entities if isinstance(entities, Sequence) else [entities]
    fig = go.Figure(
        layout=go.Layout(title=go.layout.Title(text=title))
    )
    surface_coord_groups: dict[str, list[np.ndarray]] = {}
    edge_coord_groups: dict[str, list[np.ndarray]] = {}

    for entity in entities:
        if isinstance(entity, (Volume, PlaneSurface)):
            surfaces = entity.get_surfaces() if isinstance(entity, Volume) else [entity]
            for surface in surfaces:
                surface_label = surface.label or f"Surface{surface.tag}"
                if surface.tag not in surface_coord_groups:
                    surface_coord_groups[surface_label] = []
                surface_coord_groups[surface_label] += surface.get_coords(samples_per_spline, True)
                
                for curve_loop in surface.curve_loops:
                    curve_loop_label = curve_loop.label or f"CurveLoop{curve_loop.tag}"

                    if curve_loop.tag not in edge_coord_groups:
                        edge_coord_groups[curve_loop_label] = []

                    edge_coords = curve_loop.get_coords(samples_per_spline, True)
                    edge_coord_groups[curve_loop_label].append(edge_coords)

        elif isinstance(entity, Edge):
            edge_label = entity.label or f"Edge{entity.tag}"
            if entity.tag not in edge_coord_groups:
                edge_coord_groups[edge_label] = []

            edge_coords = entity.get_coords(samples_per_spline)
            edge_coord_groups[edge_label].append(edge_coords)
        else:
            raise ValueError(f"Unknown entity type: {type(entities[0])}")


    if isinstance(entities[0], Volume):
        for label, coord_group in surface_coord_groups.items():
            for surface_coords in coord_group:
                add_plot(surface_coords, fig, label)

    if isinstance(entities[0], (Edge, PlaneSurface)):
        for label, coord_group in edge_coord_groups.items():
            edge_coords = np.array(coord_group if len(coord_group) > 1 else coord_group[0], dtype=NumpyFloat)
            add_plot(edge_coords, fig, label)


    fig.layout.yaxis.scaleanchor = "x"  # type: ignore
    fig.show()