from typing import Optional, Sequence, Union, cast
from plotly import graph_objects as go
from ezmesh.geometry.curve_loop import CurveLoop
from ezmesh.geometry.edge import Edge
from ezmesh.geometry.entity import GeoEntity
from ezmesh.geometry.plane_surface import PlaneSurface
from ezmesh.geometry.point import Point
from ezmesh.geometry.volume import Volume
import numpy.typing as npt
import numpy as np
from ezmesh.utils.types import NumpyFloat

def plot_entities(
    entities: Sequence[GeoEntity], 
    title: str = "Surface", 
    samples_per_spline: int = 20, 
):
    fig = go.Figure(
        layout=go.Layout(title=go.layout.Title(text=title))
    )
    
    exterior_coords: list[tuple[Optional[str], npt.NDArray[NumpyFloat]]] = []

    for entity in entities:
        if isinstance(entities[0], (Volume, PlaneSurface, CurveLoop)):
            exterior_coords += [(edge.label, edge.get_coords(samples_per_spline))for edge in cast(Union[Volume, PlaneSurface, CurveLoop], entity).get_edges()]
        elif isinstance(entities[0], Edge):
            exterior_coords += [(edge.label, edge.get_coords(samples_per_spline)) for edge in cast(Sequence[Edge], entities)]
        elif isinstance(entities[0], Point):
            exterior_coords += [(point.label, np.array([point.coord])) for point in cast(Sequence[Point], entities)] # type: ignore
        else:
            raise ValueError(f"Unknown entity type: {type(entities[0])}")

    for label, exterior_coord in exterior_coords:
        fig.add_scatter3d(
            x=exterior_coord[:,0],
            y=exterior_coord[:,1],
            z=exterior_coord[:,2],
            name=label,
            legendgroup=label,
        )


    fig.layout.yaxis.scaleanchor = "x"  # type: ignore
    fig.show()