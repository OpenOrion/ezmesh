# %%
from typing import List
from ezmesh import CurveLoop, TransfinitePlaneSurface, Geometry, Point, Line, TransfiniteLine, PlaneSurface,  TransfinitePlaneSurface, visualize_mesh


with Geometry() as geo:
    mesh_size = 0.05
    points = [
        Point([0, 1], mesh_size),
        Point([1.5, 1], mesh_size),
        Point([1.5, 0.2], mesh_size),
        Point([0.5, 0], mesh_size),
        Point([0, 0], mesh_size),
    ]

    lines: List[Line] = [
        TransfiniteLine(start=points[0], end=points[1], label="upper", cell_count=150),
        TransfiniteLine(start=points[1], end=points[2], label="outlet", cell_count=200),
        TransfiniteLine(start=points[2], end=points[3], label="lower", cell_count=100),
        TransfiniteLine(start=points[3], end=points[4], label="lower", cell_count=50),
        TransfiniteLine(start=points[4], end=points[0], label="inlet", cell_count=200),
    ]

    wedge_curve_loop = CurveLoop(lines=lines)
    surface = PlaneSurface(
        outlines=[wedge_curve_loop],
        is_quad_mesh=True,
        # corners=[points[0], points[1], points[2], points[4]]
    )
    mesh = geo.generate(surface)
    visualize_mesh(mesh)
    geo.write("mesh_wedge_inv.su2")


# %%
