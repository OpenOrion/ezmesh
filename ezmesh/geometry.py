from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union, cast
import numpy as np
import numpy.typing as npt
import gmsh
from ezmesh.exporters import export_to_su2
from ezmesh.utils.geometry import PropertyType, get_bspline, get_property, get_group_name, get_sampling
from ezmesh.visualizer import visualize_curve_loops
from .importers import import_from_gmsh

Number = Union[int, float]
SegmentType = Union["Line", "Curve"]
PointCoordType = Union[npt.NDArray[np.float64], Tuple[Number, Number], List[Number]]
ListOrTuple = Union[List, Tuple]
GroupType = Union[npt.NDArray[np.float64], Tuple[str, npt.NDArray[np.float64]]]


class MeshContext:
    point_registry: Dict[Tuple[float, float, float], int]

    def __init__(self) -> None:
        self.point_registry = {}


class DimType(Enum):
    POINT = 0
    CURVE = 1
    SURFACE = 2
    VOLUME = 3


class MeshTransaction:
    def __init__(self) -> None:
        self.tag: Optional[int] = None
        self.before_sync_initiated: bool = False
        self.after_sync_initiated: bool = False

    def before_sync(self, ctx: MeshContext):
        "completes transaction before syncronization and returns tag."
        self.before_sync_initiated = True

    def after_sync(self, ctx: MeshContext):
        "completes transaction after syncronization and returns tag."
        self.after_sync_initiated = True

    def reset(self):
        self.tag = None
        self.before_sync_initiated = False
        self.after_sync_initiated = False


class CurveField(MeshTransaction):
    def __init__(self) -> None:
        super().__init__()

    def before_sync(self, ctx: MeshContext, curve_loop: "CurveLoop"):
        super().before_sync(ctx)

    def after_sync(self, ctx: MeshContext, curve_loop: "CurveLoop"):
        super().after_sync(ctx)


class SurfaceField(MeshTransaction):
    def __init__(self) -> None:
        super().__init__()

    def before_sync(self, ctx: MeshContext, surface: "PlaneSurface"):
        super().before_sync(ctx)

    def after_sync(self, ctx: MeshContext, surface: "PlaneSurface"):
        super().after_sync(ctx)


@dataclass
class Point(MeshTransaction):
    coord: PointCoordType
    "coordinate of point"

    mesh_size: float
    "mesh size for point"

    label: Optional[int] = None
    "tag of point"

    def __post_init__(self):
        super().__init__()
        self.coord = np.asarray(self.coord)
        self.dim_type = DimType.POINT
        self.x = self.coord[0]
        self.y = self.coord[1]
        self.z = self.coord[2] if len(self.coord) == 3 else 0

    def before_sync(self, ctx: MeshContext):
        if not self.before_sync_initiated:
            pnt_key = (self.x, self.y, self.z)
            if (self.x, self.y, self.z) in ctx.point_registry:
                self.tag = ctx.point_registry[pnt_key]
            else:
                self.tag = gmsh.model.geo.add_point(self.x, self.y, self.z, self.mesh_size)
                ctx.point_registry[pnt_key] = self.tag
        super().before_sync(ctx)


@dataclass
class Line(MeshTransaction):
    start: Point
    "starting point of line"

    end: Point
    "ending point of line"

    label: Optional[str] = None
    "physical group label"

    def __post_init__(self):
        super().__init__()
        self.dim_type = DimType.CURVE

    def get_coords(self):
        return np.array([self.start.coord, self.end.coord])

    def before_sync(self, ctx: MeshContext):
        if not self.before_sync_initiated:
            self.start.before_sync(ctx)
            self.end.before_sync(ctx)
            self.tag = gmsh.model.geo.add_line(self.start.tag, self.end.tag)
        super().before_sync(ctx)

    def reset(self):
        super().reset()
        self.start.reset()
        self.end.reset()


@dataclass
class Curve(MeshTransaction):
    ctrl_points: List[Point]
    "control points of spline"

    type: str
    "type of curve"

    label: Optional[str] = None
    "physical group label"

    def __post_init__(self):
        super().__init__()
        self.dim_type = DimType.CURVE
        self.start = self.ctrl_points[0]
        self.end = self.ctrl_points[-1]

    def get_coords(self, num_pnts: int, is_cosine_sampling: bool):
        ctrl_point_coords = np.array([ctrl_point.coord for ctrl_point in self.ctrl_points])
        sampling = get_sampling(num_pnts, is_cosine_sampling)
        bspline = get_bspline(ctrl_point_coords, 3)
        return bspline(sampling)

    def before_sync(self, ctx: MeshContext):
        if not self.before_sync_initiated:
            ctrl_point_tags = []
            for ctrl_point in self.ctrl_points:
                ctrl_point.before_sync(ctx)
                ctrl_point_tags.append(ctrl_point.tag)

            if self.type == "BSpline":
                self.tag = gmsh.model.geo.add_bspline(ctrl_point_tags)
            elif self.type == "Spline":
                self.tag = gmsh.model.geo.add_spline(ctrl_point_tags)
            elif self.type == "Bezier":
                self.tag = gmsh.model.geo.add_bezier(ctrl_point_tags)
            else:
                raise ValueError(f"Curve type {self.type} not specified")

        super().before_sync(ctx)

    def reset(self):
        super().reset()
        for ctrl_point in self.ctrl_points:
            ctrl_point.reset()

    @staticmethod
    def from_coords(
        coords: npt.NDArray[np.float64],
        mesh_size: Union[float, List[float]],
        type: str,
        label: Optional[str] = None,
    ) -> "Curve":
        ctrl_points = []
        for i, coord in enumerate(coords):
            mesh_size = mesh_size[i] if isinstance(mesh_size, list) else mesh_size
            ctrl_points.append(Point(coord, mesh_size))
        return Curve(ctrl_points, type, label)


@dataclass
class CurveLoop(MeshTransaction):
    segments: List[SegmentType]
    "Lines of curve"

    holes: List["CurveLoop"] = field(default_factory=list)
    "hole curve loops that make up the surface"

    label: Optional[str] = None
    "physical group label"

    fields: List[CurveField] = field(default_factory=list)
    "fields to be added to the curve loop"

    def __post_init__(self):
        super().__init__()
        self.dim_type = DimType.CURVE
        self.points = []
        self.segment_groups: Dict[str, List[SegmentType]] = {}

        for segment in self.segments:
            if isinstance(segment, Curve):
                self.points += segment.ctrl_points
            else:
                self.points.append(segment.start)

            if segment.label:
                name = get_group_name(segment.label)
                if name not in self.segment_groups:
                    self.segment_groups[name] = []
                self.segment_groups[name].append(segment)

    def visualize(self):
        visualize_curve_loops([self], self.label or "Curve Loop")

    def get_exterior_coords(self, num_pnts: int, is_cosine_sampling: bool = True):
        coords = []
        for segment in self.segments:
            if isinstance(segment, Curve):
                coords.append(segment.get_coords(num_pnts, is_cosine_sampling))
            else:
                coords.append(segment.get_coords())
        return np.concatenate(coords)

    def get_points(self, group_name: str):
        return [self.segment_groups[group_name][0].start, self.segment_groups[group_name][-1].end]

    def before_sync(self, ctx: MeshContext):
        if not self.before_sync_initiated:
            segement_tags = []
            for segment in self.segments:
                segment.before_sync(ctx)
                segement_tags.append(cast(int, segment.tag))
            self.tag = gmsh.model.geo.add_curve_loop(segement_tags)

            for field in self.fields:
                field.before_sync(ctx, self)

        super().before_sync(ctx)

    def after_sync(self, ctx: MeshContext):
        if not self.after_sync_initiated:
            for segment in self.segments:
                segment.after_sync(ctx)

            for field in self.fields:
                field.after_sync(ctx, self)

        super().after_sync(ctx)

    def reset(self):
        super().reset()
        for segment in self.segments:
            segment.reset()

        for field in self.fields:
            field.reset()

    @staticmethod
    def from_coords(
        coordsOrGroups: Union[npt.NDArray[np.float64], List[GroupType]],
        mesh_size: float,
        curve_labels: Optional[Union[List[str], str]] = None,
        label: Optional[str] = None,
        holes: List["CurveLoop"] = [],
        fields: List[CurveField] = [],
    ):
        if curve_labels is None and label is not None:
            curve_labels = label
        groups = coordsOrGroups if isinstance(coordsOrGroups, list) else [coordsOrGroups]
        segments: List[SegmentType] = []
        property_index: int = 0

        prev_point = None
        first_point = None
        for group in groups:

            if isinstance(group, np.ndarray):
                coords = group
                for coord in coords:
                    # adding points
                    if (prev_point and (coord == prev_point.coord).all()):
                        continue
                    point = Point(coord, mesh_size)
                    # adding lines to connect points
                    if prev_point:
                        curve_label = get_property(curve_labels, property_index)
                        line = Line(prev_point, point, curve_label)
                        segments.append(line)
                        property_index += 1

                    if first_point is None:
                        first_point = point
                    prev_point = point
            else:
                type = group[0]
                ctrl_coords = group[1]
                if (prev_point and (ctrl_coords[0] == prev_point.coord).all()):
                    continue
                ctrl_points = [Point(ctrl_coord, mesh_size) for ctrl_coord in ctrl_coords]
                if prev_point:
                    if len(segments) > 1 and isinstance(segments[-1], Line):
                        ctrl_points = [prev_point] + ctrl_points
                    else:
                        line = Line(prev_point, ctrl_points[0], label=get_property(curve_labels, property_index))
                        segments.append(line)
                        property_index += 1
                curve_label = get_property(curve_labels, property_index)
                curve = Curve(ctrl_points, type, curve_label)
                segments.append(curve)
                property_index += 1
                prev_point = curve.end
                if first_point is None:
                    first_point = curve.start

        assert prev_point and first_point, "No points found in curve loop"
        segments.append(Line(prev_point, first_point, label=get_property(curve_labels, property_index)))

        return CurveLoop(segments, holes, label, fields)


@dataclass
class PlaneSurface(MeshTransaction):
    outlines: List[CurveLoop]
    "outline curve loop that make up the surface"

    label: Optional[str] = None
    "label for physical group surface"

    is_quad_mesh: bool = False
    "if true, surface mesh is made of quadralateral cells, else triangular cells"

    fields: List[SurfaceField] = field(default_factory=list)
    "fields to be added to the surface"

    def __post_init__(self):
        super().__init__()
        self.dim_type = DimType.SURFACE
        self.holes = [hole for outline in self.outlines for hole in outline.holes]
        self.curve_loops = self.outlines + self.holes

    def visualize(self, title: str = "Surface"):
        visualize_curve_loops(self.outlines, title)

    def before_sync(self, ctx: MeshContext):
        if not self.before_sync_initiated:
            curve_loop_tags = []
            for curve_loop in self.curve_loops:
                curve_loop.before_sync(ctx)
                curve_loop_tags.append(curve_loop.tag)
            self.tag = gmsh.model.geo.add_plane_surface(curve_loop_tags)

        super().before_sync(ctx)

    def after_sync(self, ctx: MeshContext):
        if not self.after_sync_initiated:
            segment_groups:  Dict[str, List[SegmentType]] = {}
            for curve_loop in self.curve_loops:
                curve_loop.after_sync(ctx)
                segment_groups = {**segment_groups, **curve_loop.segment_groups}
            for (name, segments) in segment_groups.items():
                segment_tags = [segment.tag for segment in segments if segment.tag is not None]
                physical_group_tag = gmsh.model.add_physical_group(DimType.CURVE.value, segment_tags)
                gmsh.model.set_physical_name(DimType.CURVE.value, physical_group_tag, name)

            physical_group_tag = gmsh.model.add_physical_group(DimType.SURFACE.value, [self.tag])
            if self.label is not None:
                gmsh.model.set_physical_name(DimType.SURFACE.value, physical_group_tag, self.label)

            if self.is_quad_mesh:
                gmsh.model.mesh.set_recombine(2, self.tag)  # type: ignore

            for field in self.fields:
                field.after_sync(ctx, self)
        super().after_sync(ctx)

    def reset(self):
        super().reset()
        for curve_loop in self.curve_loops:
            curve_loop.reset()

        for field in self.fields:
            field.reset()


@dataclass
class TransfiniteSurfaceField(SurfaceField):
    """
    A plane surface with transfinite meshing. Normal plane if corners are not defined.
    """
    corners: Optional[List[Point]] = None
    "corners of transfinite surface"

    arrangement: str = "Left"
    "arrangement of transfinite surface"

    def __post_init__(self):
        return super().__init__()

    def after_sync(self, ctx: MeshContext, surface: "PlaneSurface"):
        if not self.after_sync_initiated and self.corners is not None:
            corner_tags: List[int] = []
            for corner in self.corners:
                corner_tags.append(cast(int, corner.tag))
            gmsh.model.mesh.set_transfinite_surface(surface.tag, self.arrangement, cornerTags=corner_tags)

        super().after_sync(ctx, surface)


@dataclass
class BoundaryLayerField(CurveField):
    aniso_max: Optional[float] = None
    "threshold angle for creating a mesh fan in the boundary layer"

    hfar: Optional[float] = None
    "element size far from the wall"

    hwall_n: Optional[float] = None
    "mesh Size Normal to the The Wal"

    ratio: Optional[float] = None
    "size Ratio Between Two Successive Layers"

    thickness: Optional[float] = None
    "maximal thickness of the boundary layer"

    intersect_metrics: bool = False
    "intersect metrics of all surfaces"

    is_quad_mesh: bool = False
    "generate recombined elements in the boundary layer"

    def __post_init__(self):
        super().__init__()

    def after_sync(self, ctx: MeshContext, curve_loop: CurveLoop):
        if not self.after_sync_initiated:
            self.tag = gmsh.model.mesh.field.add('BoundaryLayer')
            segement_tags = [segement.tag for segement in curve_loop.segments]
            gmsh.model.mesh.field.setNumbers(self.tag, 'CurvesList', segement_tags)
            if self.aniso_max:
                gmsh.model.mesh.field.setNumber(self.tag, "AnisoMax", self.aniso_max)
            if self.intersect_metrics:
                gmsh.model.mesh.field.setNumber(self.tag, "IntersectMetrics", self.intersect_metrics)
            if self.is_quad_mesh:
                gmsh.model.mesh.field.setNumber(self.tag, "Quads", int(self.is_quad_mesh))
            if self.hfar:
                gmsh.model.mesh.field.setNumber(self.tag, "hfar", self.hfar)
            if self.hwall_n:
                gmsh.model.mesh.field.setNumber(self.tag, "hwall_n", self.hwall_n)
            if self.ratio:
                gmsh.model.mesh.field.setNumber(self.tag, "ratio", self.ratio)
            if self.thickness:
                gmsh.model.mesh.field.setNumber(self.tag, "thickness", self.thickness)

            gmsh.model.mesh.field.setAsBoundaryLayer(self.tag)
        super().after_sync(ctx, curve_loop)


@dataclass
class TransfiniteCurveField(CurveField):
    node_counts: PropertyType[int]
    "number per curve"

    mesh_types: Optional[PropertyType[str]] = None
    "mesh type for each curve"

    coefs: Optional[PropertyType[float]] = None
    "coefficients for each curve"

    def __post_init__(self):
        super().__init__()
        self.dim_type = DimType.CURVE

    def after_sync(self, ctx: MeshContext, curve_loop: CurveLoop):
        if not self.after_sync_initiated:
            for i, segment in enumerate(curve_loop.segments):
                gmsh.model.mesh.set_transfinite_curve(
                    segment.tag,
                    numNodes=get_property(self.node_counts, i, segment.label)+1,
                    meshType=get_property(self.mesh_types, i, segment.label, "Progression"),
                    coef=get_property(self.coefs, i, segment.label, 1.0)
                )
        super().after_sync(ctx, curve_loop)


class Geometry:
    def __enter__(self):
        self.ctx = MeshContext()
        gmsh.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        gmsh.finalize()

    def generate(self, transactions: Union[MeshTransaction, List[MeshTransaction]]):
        if isinstance(transactions, list):
            for transaction in transactions:
                transaction.before_sync(self.ctx)
        else:
            transactions.before_sync(self.ctx)
        gmsh.model.geo.synchronize()
        if isinstance(transactions, list):
            for transaction in transactions:
                transaction.after_sync(self.ctx)
        else:
            transactions.after_sync(self.ctx)
        gmsh.option.set_number("General.ExpertMode", 1)
        gmsh.model.mesh.generate()
        self.mesh = import_from_gmsh()

        if isinstance(transactions, list):
            for transaction in transactions:
                transaction.reset()
        else:
            transactions.reset()

        return self.mesh

    def write(self, filename: str):
        if filename.endswith(".su2"):
            export_to_su2(self.mesh, filename)
        else:
            gmsh.write(filename)
