from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import trimesh


def _build_components_from_segments(segments: np.ndarray) -> List[Dict[str, Any]]:
    if segments is None or len(segments) == 0:
        return []
    path = trimesh.load_path(np.asarray(segments))
    components: List[Dict[str, Any]] = []
    for poly in path.discrete:
        pts = np.asarray(poly, dtype=np.float64)
        if pts.shape[0] < 3:
            continue
        if np.linalg.norm(pts[0] - pts[-1]) > 1e-6:
            pts = np.vstack([pts, pts[0]])
        perim = float(np.linalg.norm(pts[1:] - pts[:-1], axis=1).sum())
        components.append({"points": pts, "perimeter_m": perim})
    return components


def _polyline_length(points: np.ndarray) -> float:
    if points is None or points.shape[0] < 2:
        return 0.0
    diffs = points[1:] - points[:-1]
    return float(np.linalg.norm(diffs, axis=1).sum())


def _filter_segment_indices_by_body_parts(
    sliced_faces: np.ndarray,
    body_parts: Optional[Sequence[str]],
    face_segmentation: Optional[Dict[str, List[int]]],
) -> np.ndarray:
    if body_parts is None or face_segmentation is None:
        return np.arange(len(sliced_faces), dtype=np.int64)
    allowed_faces = set()
    for part in body_parts:
        for face_idx in face_segmentation.get(part, []):
            allowed_faces.add(int(face_idx))
    if not allowed_faces:
        return np.arange(len(sliced_faces), dtype=np.int64)
    keep = [i for i, f in enumerate(sliced_faces) if int(f) in allowed_faces]
    return np.asarray(keep, dtype=np.int64)


def _loop_center_distance(loop: np.ndarray, target_point: Optional[np.ndarray]) -> float:
    if target_point is None:
        return 0.0
    center = np.mean(loop, axis=0)
    return float(np.linalg.norm(center - target_point))


def slice_circumference_cm(
    vertices: np.ndarray,
    faces: np.ndarray,
    plane_origin: np.ndarray,
    plane_normal: np.ndarray,
    target_point: Optional[np.ndarray] = None,
    body_parts: Optional[Sequence[str]] = None,
    face_segmentation: Optional[Dict[str, List[int]]] = None,
    allow_filter_relax: bool = False,
) -> Dict[str, Any]:
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    segments, sliced_faces = trimesh.intersections.mesh_plane(
        mesh,
        plane_normal=np.asarray(plane_normal, dtype=np.float64),
        plane_origin=np.asarray(plane_origin, dtype=np.float64),
        return_faces=True,
    )

    if segments is None or len(segments) == 0:
        return {
            "value_cm": None,
            "loop_count": 0,
            "selected_loop_length_cm": None,
            "failure_reason": "no_mesh_plane_segments",
            "segments_before_filter": 0,
            "segments_after_filter": 0,
            "filter_relaxed": False,
        }

    segments_before = int(len(segments))
    selected_indices = _filter_segment_indices_by_body_parts(
        np.asarray(sliced_faces),
        body_parts=body_parts,
        face_segmentation=face_segmentation,
    )
    if selected_indices.size == 0:
        selected_indices = np.arange(len(segments), dtype=np.int64)

    selected_segments = np.asarray(segments)[selected_indices]
    segments_after = int(len(selected_segments))
    components = _build_components_from_segments(selected_segments)
    filter_relaxed = False
    if (
        not components
        and allow_filter_relax
        and body_parts is not None
        and len(selected_segments) < len(segments)
    ):
        # Surgical fallback: body-part filtering may fragment loops; retry unfiltered.
        selected_segments = np.asarray(segments)
        components = _build_components_from_segments(selected_segments)
        filter_relaxed = True
        segments_after = int(len(selected_segments))

    if not components:
        return {
            "value_cm": None,
            "loop_count": 0,
            "selected_loop_length_cm": None,
            "failure_reason": "no_closed_loops",
            "segments_before_filter": segments_before,
            "segments_after_filter": segments_after,
            "filter_relaxed": filter_relaxed,
        }

    # Rule: nearest to target point; tie-break by longest loop.
    scored = []
    for comp in components:
        dist = _loop_center_distance(comp["points"], target_point=target_point)
        length_m = float(comp["perimeter_m"])
        scored.append((dist, -length_m, length_m))
    scored.sort(key=lambda x: (x[0], x[1]))
    _, _, best_len_m = scored[0]

    return {
        "value_cm": round(float(best_len_m * 100.0), 1),
        "loop_count": len(components),
        "selected_loop_length_cm": round(float(best_len_m * 100.0), 1),
        "failure_reason": None,
        "segments_before_filter": segments_before,
        "segments_after_filter": segments_after,
        "filter_relaxed": filter_relaxed,
    }
