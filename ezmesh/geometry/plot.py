from typing import Sequence, Union
from plotly import graph_objects as go
from ezmesh.geometry.transactions.curve import Curve
from ezmesh.geometry.transaction import GeoEntity
from ezmesh.geometry.transactions.curve_loop import CurveLoop
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
    curve_coord_groups: dict[str, list[np.ndarray]] = {}

    for entity in entities:
        if isinstance(entity, (Volume, PlaneSurface, CurveLoop, Curve)):
            for curve in entity.curves:
                curve_label = curve.label or f"Curve{curve.tag}"
                curve_coords = curve.get_coords(samples_per_spline)
                if curve_label not in curve_coord_groups:
                    curve_coord_groups[curve_label] = []
                curve_coord_groups[curve_label].append(curve_coords)
        else:
            raise ValueError(f"Unknown entity type: {type(entities[0])}")


    for label, curve_coord_group in (curve_coord_groups.items()):
        curve_coords = np.concatenate(curve_coord_group, dtype=NumpyFloat)
        add_plot(curve_coords, fig, label)


    fig.layout.yaxis.scaleanchor = "x"  # type: ignore
    fig.show()