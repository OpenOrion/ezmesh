import gmsh
from typing import Iterable, Sequence, Union
from plotly import graph_objects as go
import numpy as np
from ezmesh.transactions.transaction import DimType, Entity, Transaction
from ezmesh.utils.shapes import add_plot, get_sampling
from ezmesh.utils.types import NumpyFloat



def get_parametric_coords(curve: Entity, num_pnts: int, is_cosine_sampling: bool=False):
    assert curve.dim_type == DimType.CURVE, "Only curves are supported"
    bounds = gmsh.model.getParametrizationBounds(DimType.CURVE.value, curve.tag)
    sampling = get_sampling(bounds[0][0], bounds[1][0], num_pnts, is_cosine_sampling)
    coords_concatted = gmsh.model.getValue(DimType.CURVE.value, curve.tag, sampling)
    coords = np.array(coords_concatted, dtype=NumpyFloat).reshape((-1, 3))
    return coords

# def plot_entities(
#     entities: Union[Entity, Sequence[Entity]], 
#     title: str = "Plot", 
#     samples_per_spline: int = 50, 
# ):
#     entities = entities if isinstance(entities, Sequence) else [entities]
#     fig = go.Figure(
#         layout=go.Layout(title=go.layout.Title(text=title))
#     )
#     curve_coord_groups: dict[str, list[np.ndarray]] = {}

#     for entity in entities:
#         for curve in entity.curves:
#             curve_label = curve.label or f"Curve{curve.tag}"
#             curve_coords = get_parametric_coords(curve, samples_per_spline)
#             if curve_label not in curve_coord_groups:
#                 curve_coord_groups[curve_label] = []
#             curve_coord_groups[curve_label].append(curve_coords)

#     for label, curve_coord_group in (curve_coord_groups.items()):
#         curve_coords = np.concatenate(curve_coord_group, dtype=NumpyFloat)
#         add_plot(curve_coords, fig, label)

#     fig.layout.yaxis.scaleanchor = "x"  # type: ignore
#     fig.show()

