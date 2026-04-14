"""
Measurement Extraction Service (SMPL-Based)
============================================

Extracts 15 body measurements from front and side pose images using:
  1. MediaPipe → 2D pose keypoints
  2. SMPL optimization → fit body shape (betas) to match keypoints
  3. SMPL mesh → vertex-based anthropometric measurements

This approach estimates the UNDERLYING body shape beneath clothing
by using a statistical body model trained on thousands of 3D body scans.

Dependencies (all pip-installable):
  pip install torch smplx mediapipe opencv-python numpy Pillow scipy trimesh

External Model Files Required:
  - SMPL model files: SMPL_MALE.pkl, SMPL_FEMALE.pkl, SMPL_NEUTRAL.pkl
    Download from: https://smpl.is.tue.mpg.de (free registration)
    Place in: data/body_models/smpl/ (cleaned of chumpy objects)
"""

import os
import math
import logging
from io import BytesIO
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

from app.config import get_settings
from app.services.shapy_client import (
    SHAPYClient,
    SHAPYClientError,
    SHAPYServiceUnavailableError,
)

logger = logging.getLogger(__name__)
settings = get_settings()

# ============================================================================
# Configuration
# ============================================================================

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


# ============================================================================
# Stage 1: Image → 2D Keypoints (MediaPipe)
# ============================================================================

class PoseDetector:
    """
    Detects 2D body keypoints using MediaPipe Pose.
    Returns normalized (x, y) coordinates + visibility scores.
    """

    def __init__(self):
        self._pose = None

    def _lazy_load(self):
        if self._pose is not None:
            return
        import mediapipe as mp
        self._mp_pose = mp.solutions.pose
        self._pose = self._mp_pose.Pose(
            static_image_mode=True,
            model_complexity=2,
            min_detection_confidence=0.5,
        )
        logger.info("MediaPipe Pose loaded")

    def detect(self, image_data: bytes) -> Optional[Dict]:
        """
        Detect pose landmarks from image bytes.

        Returns:
            Dict with 'landmarks' (33x3 array of x,y,visibility)
            and 'image_shape' (H, W), or None if no person detected.
        """
        self._lazy_load()

        img = Image.open(BytesIO(image_data)).convert("RGB")
        img_np = np.array(img)
        img_rgb = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        img_rgb = cv2.cvtColor(img_rgb, cv2.COLOR_BGR2RGB)

        results = self._pose.process(img_rgb)

        if not results.pose_landmarks:
            return None

        landmarks = []
        for lm in results.pose_landmarks.landmark:
            landmarks.append([lm.x, lm.y, lm.visibility])

        return {
            "landmarks": np.array(landmarks),  # (33, 3) - x, y, visibility
            "image_shape": img_np.shape[:2],    # (H, W)
        }

    def __del__(self):
        if self._pose is not None:
            self._pose.close()


# ============================================================================
# Stage 2: 2D Keypoints → SMPL betas (Optimization)
# ============================================================================

# Mapping: MediaPipe landmark index → SMPL joint index
# MediaPipe has 33 landmarks, SMPL has 24 joints
# We map the ones that correspond
MEDIAPIPE_TO_SMPL = {
    0: 15,   # Nose → Head
    11: 16,  # Left Shoulder → L_Shoulder
    12: 17,  # Right Shoulder → R_Shoulder
    13: 18,  # Left Elbow → L_Elbow
    14: 19,  # Right Elbow → R_Elbow
    15: 20,  # Left Wrist → L_Wrist
    16: 21,  # Right Wrist → R_Wrist
    23: 1,   # Left Hip → L_Hip
    24: 2,   # Right Hip → R_Hip
    25: 4,   # Left Knee → L_Knee
    26: 5,   # Right Knee → R_Knee
    27: 7,   # Left Ankle → L_Ankle
    28: 8,   # Right Ankle → R_Ankle
}


class SMPLShapeFitter:
    """
    Fits SMPL shape parameters (betas) to 2D keypoints by optimizing
    the reprojection error. This estimates the body shape that best
    explains the observed 2D joint positions.
    """

    def __init__(self):
        self._model_cache = {}

    def _get_smpl_model(self, gender: str):
        """Get or create SMPL model for given gender."""
        if gender not in self._model_cache:
            import smplx
            model = smplx.create(
                model_path=settings.SMPL_MODEL_DIR,
                model_type="smpl",
                gender=gender,
                batch_size=1,
            ).to(DEVICE)
            self._model_cache[gender] = model
            logger.info(f"SMPL model loaded for gender={gender}")
        return self._model_cache[gender]

    def fit(
        self,
        landmarks_2d: np.ndarray,
        image_shape: Tuple[int, int],
        gender: str,
        height_cm: float,
        num_iterations: int = 100,
    ) -> Tuple[np.ndarray, float]:
        """
        Fit SMPL betas to 2D keypoints.

        Args:
            landmarks_2d: (33, 3) MediaPipe landmarks (x, y, visibility)
            image_shape: (H, W) of the image
            gender: 'male', 'female', or 'neutral'
            height_cm: Known height for scale constraint
            num_iterations: Optimization steps

        Returns:
            Tuple of (betas: np.ndarray shape (10,), confidence: float)
        """
        model = self._get_smpl_model(gender)
        H, W = image_shape

        # Extract matched 2D keypoints
        target_2d = []
        smpl_joint_indices = []
        weights = []

        for mp_idx, smpl_idx in MEDIAPIPE_TO_SMPL.items():
            x, y, vis = landmarks_2d[mp_idx]
            if vis > 0.3:  # Only use visible keypoints
                # Convert normalized coords to pixel coords
                target_2d.append([x * W, y * H])
                smpl_joint_indices.append(smpl_idx)
                weights.append(vis)

        if len(target_2d) < 6:
            raise ValueError(
                f"Only {len(target_2d)} keypoints detected with sufficient "
                f"visibility. Need at least 6 for shape fitting."
            )

        target_2d = torch.tensor(target_2d, dtype=torch.float32, device=DEVICE)
        weights = torch.tensor(weights, dtype=torch.float32, device=DEVICE)
        weights = weights / weights.sum()

        # Optimization variables
        betas = torch.zeros(1, 10, dtype=torch.float32, device=DEVICE, requires_grad=True)
        # Weak perspective camera: [scale, tx, ty]
        camera = torch.tensor([[1.0, 0.0, 0.0]], dtype=torch.float32, device=DEVICE, requires_grad=True)

        optimizer = torch.optim.Adam([betas, camera], lr=0.01)

        best_loss = float("inf")
        best_betas = None

        for i in range(num_iterations):
            optimizer.zero_grad()

            # Forward SMPL
            output = model(betas=betas, return_verts=True)
            joints_3d = output.joints[0]  # (J, 3)

            # Select matched joints
            selected_joints = joints_3d[smpl_joint_indices]  # (N, 3)

            # Weak perspective projection: 2D = scale * (X, Y) + (tx, ty)
            scale = camera[0, 0]
            tx = camera[0, 1]
            ty = camera[0, 2]

            proj_x = scale * selected_joints[:, 0] * W / 2 + W / 2 + tx
            proj_y = scale * selected_joints[:, 1] * H / 2 + H / 2 + ty
            projected_2d = torch.stack([proj_x, proj_y], dim=1)

            # Reprojection loss (weighted)
            reproj_loss = (weights.unsqueeze(1) * (projected_2d - target_2d) ** 2).sum()

            # Beta regularization (prefer average body shape)
            reg_loss = 0.001 * (betas ** 2).sum()

            # Height constraint
            verts = output.vertices[0]
            model_height_m = verts[:, 1].max() - verts[:, 1].min()
            height_loss = 0.1 * (model_height_m - height_cm / 100.0) ** 2

            loss = reproj_loss + reg_loss + height_loss
            loss.backward()
            optimizer.step()

            if loss.item() < best_loss:
                best_loss = loss.item()
                best_betas = betas.detach().clone()

        # Compute confidence from reprojection error
        final_betas = best_betas.cpu().numpy().flatten()
        # Lower error = higher confidence
        error = best_loss
        confidence = max(0.5, min(0.95, 1.0 - error / 50.0))

        logger.info(
            f"Shape fitting complete: loss={best_loss:.4f}, "
            f"confidence={confidence:.2f}, "
            f"beta_norm={np.linalg.norm(final_betas):.2f}"
        )

        return final_betas, confidence


# ============================================================================
# Stage 3: SMPL betas → Body Measurements
# ============================================================================

class SMPLMeasurer:
    """
    Extracts anthropometric measurements from SMPL body model.

    Two modes:
      1. SMPL-Anthropometry library (if available) — most accurate
      2. Vertex-based fallback using smplx — good accuracy
    """

    def __init__(self):
        self._smpl_anthropometry_available = None
        self._model_cache = {}

    def _check_smpl_anthropometry(self) -> bool:
        """Check if SMPL-Anthropometry library is importable."""
        if self._smpl_anthropometry_available is not None:
            return self._smpl_anthropometry_available

        try:
            import sys
            libs_dir = os.path.join(
                os.path.dirname(__file__), "..", "..", "libs", "smpl_anthropometry"
            )
            libs_dir = os.path.abspath(libs_dir)
            if os.path.isdir(libs_dir) and libs_dir not in sys.path:
                sys.path.insert(0, libs_dir)

            from measure import MeasureBody
            self._smpl_anthropometry_available = True
            logger.info("SMPL-Anthropometry library available")
        except ImportError:
            self._smpl_anthropometry_available = False
            logger.info("SMPL-Anthropometry not available, using vertex fallback")

        return self._smpl_anthropometry_available

    def _get_smpl_model(self, gender: str):
        if gender not in self._model_cache:
            import smplx
            self._model_cache[gender] = smplx.create(
                model_path=settings.SMPL_MODEL_DIR,
                model_type="smpl",
                gender=gender,
                batch_size=1,
            ).to(DEVICE)
        return self._model_cache[gender]

    def measure(
        self,
        betas: np.ndarray,
        gender: str,
        height_cm: float,
    ) -> Dict[str, Optional[float]]:
        """
        Extract 15 measurements from SMPL betas.

        Args:
            betas: Shape parameters, shape (10,)
            gender: 'male', 'female', 'neutral'
            height_cm: Known height for scaling

        Returns:
            Dict of measurement name → value in cm
        """
        if self._check_smpl_anthropometry():
            try:
                return self._measure_with_library(betas, gender, height_cm)
            except Exception as e:
                logger.warning(f"SMPL-Anthropometry failed ({e}), using fallback")

        return self._measure_from_vertices(betas, gender, height_cm)

    def _measure_with_library(
        self, betas: np.ndarray, gender: str, height_cm: float
    ) -> Dict[str, Optional[float]]:
        """Use SMPL-Anthropometry for precise plane-cut measurements."""
        from measure import MeasureBody
        from measurement_definitions import STANDARD_LABELS

        measurer = MeasureBody("smpl")
        shape_tensor = torch.tensor(betas, dtype=torch.float32).unsqueeze(0)
        measurer.from_body_model(gender=gender, shape=shape_tensor)

        measurement_names = measurer.all_possible_measurements
        measurer.measure(measurement_names)
        measurer.height_normalize_measurements(height_cm)
        measurer.label_measurements(STANDARD_LABELS)

        labeled = measurer.labeled_measurements

        # Map library labels → API names
        label_map = {
            "height":                    "height",
            "shoulder breadth":          "shoulder_width",
            "arm right length":          "arm_length",
            "shoulder to crotch height": "torso_length",
            "inside leg height":         "inseam",
            "chest circumference":       "chest",
            "waist circumference":       "waist",
            "hip circumference":         "hip",
            "neck circumference":        "neck",
            "thigh left circumference":  "thigh",
            "bicep right circumference": "upper_arm",
            "wrist right circumference": "wrist",
            "calf left circumference":   "calf",
            "ankle left circumference":  "ankle",
            "forearm right circumference": "bicep",
        }

        result = {}
        for lib_name, api_name in label_map.items():
            val = labeled.get(lib_name)
            result[api_name] = round(val, 1) if val is not None else None

        result["height"] = height_cm
        return result

    def _measure_from_vertices(
        self, betas: np.ndarray, gender: str, height_cm: float
    ) -> Dict[str, Optional[float]]:
        """
        Generate SMPL mesh and compute measurements from vertex positions.

        Key insight: SMPL default pose is T-pose (arms horizontal).
        - Torso/legs: horizontal Y-level slicing works fine
        - Arms: must slice PERPENDICULAR to the arm bone, not horizontally
        - Neck: must filter out nearby shoulder vertices
        """
        from scipy.spatial import ConvexHull

        model = self._get_smpl_model(gender)

        betas_tensor = torch.tensor(
            betas, dtype=torch.float32, device=DEVICE
        ).unsqueeze(0)

        with torch.no_grad():
            output = model(betas=betas_tensor, return_verts=True)

        verts = output.vertices[0].cpu().numpy()  # (6890, 3)
        joints = output.joints[0].cpu().numpy()

        # Scale factor: SMPL outputs in meters, match real height
        model_height_m = verts[:, 1].max() - verts[:, 1].min()
        scale = (height_cm / 100.0) / model_height_m if model_height_m > 0 else 1.0

        verts_scaled = verts * scale
        joints_scaled = joints * scale

        # --- Length measurements ---
        def dist(j1, j2):
            return float(np.linalg.norm(joints_scaled[j1] - joints_scaled[j2])) * 100

        shoulder_width = dist(16, 17)
        arm_length = dist(17, 19) + dist(19, 21)
        torso_length = dist(12, 0)
        inseam = dist(1, 7)

        # --- Helper: convex hull perimeter ---
        def hull_perimeter(pts_2d: np.ndarray) -> Optional[float]:
            if len(pts_2d) < 3:
                return None
            try:
                hull = ConvexHull(pts_2d)
                hull_pts = pts_2d[hull.vertices]
                perim = 0.0
                for i in range(len(hull_pts)):
                    j = (i + 1) % len(hull_pts)
                    perim += np.linalg.norm(hull_pts[j] - hull_pts[i])
                return perim
            except Exception:
                return None

        def ellipse_circumference(pts_2d: np.ndarray) -> Optional[float]:
            """
            Fit an ellipse to 2D points and return its circumference.
            More robust than convex hull for body cross-sections because
            it smooths out vertex noise and handles concavities properly.
            Uses Ramanujan's approximation for ellipse perimeter.
            """
            if len(pts_2d) < 5:
                return None
            try:
                # Compute the covariance-based ellipse
                # Center the points
                center = pts_2d.mean(axis=0)
                centered = pts_2d - center

                # Covariance matrix gives us the ellipse axes
                cov = np.cov(centered.T)
                eigenvalues, _ = np.linalg.eigh(cov)

                # Semi-axes: sqrt(eigenvalue) gives std dev, but for the
                # bounding ellipse we want to cover the actual body outline.
                # Use the max extent along each eigenvector direction.
                eigenvectors = np.linalg.eigh(cov)[1]
                projected = centered @ eigenvectors
                # Semi-axes from the range of projected points
                a = (projected[:, 0].max() - projected[:, 0].min()) / 2
                b = (projected[:, 1].max() - projected[:, 1].min()) / 2

                if a < 1e-6 or b < 1e-6:
                    return None

                # Ramanujan's approximation for ellipse perimeter
                h = ((a - b) ** 2) / ((a + b) ** 2)
                perimeter = math.pi * (a + b) * (1 + 3 * h / (10 + math.sqrt(4 - 3 * h)))

                return perimeter
            except Exception:
                return None

        # =============================================================
        # TORSO circumferences: horizontal slice + ellipse fitting
        # Uses tighter arm exclusion based on actual torso boundary
        # =============================================================
        def circumference_torso(y_level, tol=0.012):
            mask = np.abs(verts_scaled[:, 1] - y_level) < tol
            for _ in range(3):
                if mask.sum() >= 20:
                    break
                tol *= 1.5
                mask = np.abs(verts_scaled[:, 1] - y_level) < tol
            if mask.sum() < 6:
                return None

            pts_3d = verts_scaled[mask]

            # Exclude arm vertices using tighter bounds
            # The actual torso edge is INSIDE the shoulder joint position.
            # Use ~80% of shoulder width as the torso boundary.
            shoulder_half_width = abs(
                joints_scaled[16, 0] - joints_scaled[17, 0]
            ) / 2
            torso_half_width = shoulder_half_width * 0.75
            center_x = (joints_scaled[16, 0] + joints_scaled[17, 0]) / 2
            torso_mask = np.abs(pts_3d[:, 0] - center_x) < torso_half_width

            if torso_mask.sum() < 6:
                torso_mask = np.ones(len(pts_3d), dtype=bool)

            pts = pts_3d[torso_mask][:, [0, 2]]  # X, Z plane

            # Use ellipse fitting (more accurate for body cross-sections)
            perim = ellipse_circumference(pts)
            if perim is not None:
                return round(perim * 100, 1)  # meters → cm, no correction needed

            # Fallback to convex hull
            perim = hull_perimeter(pts)
            if perim is None:
                return None
            return round(perim * 100, 1)

        # =============================================================
        # NECK: slice ABOVE the neck joint (12) to avoid shoulder area
        # The neck joint in SMPL is at the base of the neck where it
        # meets the shoulders. We need to measure higher up.
        # =============================================================
        def circumference_neck_fn():
            # Measure at 60% of the way from neck joint (12) to head (15)
            neck_pos = joints_scaled[12]
            head_pos = joints_scaled[15]
            measure_point = neck_pos + 0.6 * (head_pos - neck_pos)
            y_level = measure_point[1]

            tol = 0.006
            mask = np.abs(verts_scaled[:, 1] - y_level) < tol
            for _ in range(4):
                if mask.sum() >= 8:
                    break
                tol *= 1.3
                mask = np.abs(verts_scaled[:, 1] - y_level) < tol
            if mask.sum() < 4:
                return None

            pts_3d = verts_scaled[mask]

            # Filter to center — neck is narrow
            center_x = 0.0
            neck_mask = np.abs(pts_3d[:, 0] - center_x) < 0.05 * scale
            if neck_mask.sum() < 4:
                dists = np.abs(pts_3d[:, 0] - center_x)
                threshold = np.percentile(dists, 50)
                neck_mask = dists <= threshold
            if neck_mask.sum() < 3:
                return None

            pts = pts_3d[neck_mask][:, [0, 2]]

            perim = ellipse_circumference(pts)
            if perim is not None:
                return round(perim * 100, 1)

            perim = hull_perimeter(pts)
            if perim is None:
                return None
            return round(perim * 100, 1)

        # =============================================================
        # LEG circumferences: Y-level slice, one side only
        # =============================================================
        def circumference_leg(y_level, joint_3d, tol=0.012, max_radius=0.10):
            """
            Slice at y_level, keep only vertices near the given joint
            using 3D distance (not just X) to properly isolate one limb.
            """
            mask = np.abs(verts_scaled[:, 1] - y_level) < tol
            for _ in range(3):
                if mask.sum() >= 10:
                    break
                tol *= 1.5
                mask = np.abs(verts_scaled[:, 1] - y_level) < tol
            if mask.sum() < 4:
                return None

            pts_3d = verts_scaled[mask]

            # Use XZ distance from joint (ignore Y since we already sliced)
            joint_xz = np.array([joint_3d[0], joint_3d[2]])
            pts_xz = pts_3d[:, [0, 2]]
            dists = np.linalg.norm(pts_xz - joint_xz, axis=1)
            side_mask = dists < max_radius * scale

            if side_mask.sum() < 4:
                threshold = np.percentile(dists, 40)
                side_mask = dists <= threshold

            pts = pts_3d[side_mask][:, [0, 2]]
            if len(pts) < 3:
                return None

            perim = ellipse_circumference(pts)
            if perim is not None:
                return round(perim * 100, 1)

            perim = hull_perimeter(pts)
            if perim is None:
                return None
            return round(perim * 100 * 1.05, 1)

        # =============================================================
        # ARM circumferences: slice PERPENDICULAR to arm bone
        # In T-pose, arms extend along X-axis, so we slice in the
        # Y-Z plane at a given X position along the arm.
        # =============================================================
        def circumference_arm(point_along_arm, joint_start, joint_end, radius=0.05):
            """
            Measure arm circumference by:
            1. Define the arm bone direction (joint_start → joint_end)
            2. Find a point along this bone at the desired fraction
            3. Select vertices close to this point
            4. Project them onto the plane perpendicular to the bone
            5. Compute convex hull perimeter in that plane

            Args:
                point_along_arm: 3D point on the arm bone where to measure
                joint_start: 3D position of the proximal joint
                joint_end: 3D position of the distal joint
                radius: max distance from the bone axis (in scaled meters)
            """
            # Bone direction
            bone = joint_end - joint_start
            bone_len = np.linalg.norm(bone)
            if bone_len < 1e-6:
                return None
            bone_dir = bone / bone_len

            # For each vertex, compute:
            # 1. Distance along the bone from the measurement point
            # 2. Distance from the bone axis (perpendicular distance)
            vecs = verts_scaled - point_along_arm  # (6890, 3)
            along = vecs @ bone_dir  # projection along bone
            perp_vecs = vecs - np.outer(along, bone_dir)  # perpendicular component
            perp_dist = np.linalg.norm(perp_vecs, axis=1)

            # Select vertices that are:
            # - Within a thin slab along the bone (±tol)
            # - Within reasonable perpendicular distance (the limb radius)
            slab_tol = 0.015 * scale  # ±1.5cm slab thickness
            mask = (np.abs(along) < slab_tol) & (perp_dist < radius * scale)

            # Widen slab if too few points
            for _ in range(3):
                if mask.sum() >= 8:
                    break
                slab_tol *= 1.5
                mask = (np.abs(along) < slab_tol) & (perp_dist < radius * scale)

            if mask.sum() < 3:
                return None

            # Project selected vertices onto the perpendicular plane
            # We need 2D coordinates in the plane. Use two orthogonal
            # vectors perpendicular to the bone.
            # Pick an arbitrary vector not parallel to bone_dir
            if abs(bone_dir[0]) < 0.9:
                arbitrary = np.array([1, 0, 0])
            else:
                arbitrary = np.array([0, 1, 0])

            u = np.cross(bone_dir, arbitrary)
            u = u / np.linalg.norm(u)
            v = np.cross(bone_dir, u)
            v = v / np.linalg.norm(v)

            # Project perpendicular vectors onto u, v to get 2D coords
            selected_perp = perp_vecs[mask]
            pts_2d = np.column_stack([
                selected_perp @ u,
                selected_perp @ v,
            ])

            perim = hull_perimeter(pts_2d)
            if perim is None:
                return None
            return round(perim * 100 * 1.08, 1)

        # =============================================================
        # Compute all measurements
        # =============================================================

        # Joint indices: 0=Pelvis, 1=L_Hip, 2=R_Hip, 3=Spine1,
        # 4=L_Knee, 5=R_Knee, 6=Spine2, 7=L_Ankle, 8=R_Ankle,
        # 9=Spine3, 12=Neck, 15=Head, 16=L_Shoulder, 17=R_Shoulder,
        # 18=L_Elbow, 19=R_Elbow, 20=L_Wrist, 21=R_Wrist

        # Torso
        chest = circumference_torso(joints_scaled[9, 1])
        waist = circumference_torso(
            (joints_scaled[6, 1] + joints_scaled[0, 1]) / 2
        )
        hip = circumference_torso(joints_scaled[0, 1])

        # Neck — measured above the joint toward the head
        neck = circumference_neck_fn()

        # Legs — left side
        thigh = circumference_leg(
            y_level=(joints_scaled[1, 1] + joints_scaled[4, 1]) / 2,
            joint_3d=joints_scaled[1],
            tol=0.012,
            max_radius=0.10,
        )
        calf = circumference_leg(
            y_level=(joints_scaled[4, 1] + joints_scaled[7, 1]) / 2,
            joint_3d=joints_scaled[4],
            tol=0.012,
            max_radius=0.08,
        )
        ankle = circumference_leg(
            y_level=joints_scaled[7, 1],
            joint_3d=joints_scaled[7],
            tol=0.008,
            max_radius=0.05,
        )

        # Arms — use LEFT arm, perpendicular slicing
        # Upper arm: midpoint between shoulder (16) and elbow (18)
        upper_arm_point = (joints_scaled[16] + joints_scaled[18]) / 2
        upper_arm = circumference_arm(
            point_along_arm=upper_arm_point,
            joint_start=joints_scaled[16],
            joint_end=joints_scaled[18],
            radius=0.06,
        )

        # Bicep/forearm: midpoint between elbow (18) and wrist (20)
        forearm_point = (joints_scaled[18] + joints_scaled[20]) / 2
        bicep = circumference_arm(
            point_along_arm=forearm_point,
            joint_start=joints_scaled[18],
            joint_end=joints_scaled[20],
            radius=0.05,
        )

        # Wrist: near wrist joint (20)
        wrist_point = joints_scaled[20]
        wrist = circumference_arm(
            point_along_arm=wrist_point,
            joint_start=joints_scaled[18],
            joint_end=joints_scaled[20],
            radius=0.04,
        )

        return {
            "height": height_cm,
            "shoulder_width": round(shoulder_width, 1),
            "arm_length": round(arm_length, 1),
            "torso_length": round(torso_length, 1),
            "inseam": round(inseam, 1),
            "chest": chest,
            "waist": waist,
            "hip": hip,
            "neck": neck,
            "thigh": thigh,
            "upper_arm": upper_arm,
            "wrist": wrist,
            "calf": calf,
            "ankle": ankle,
            "bicep": bicep,
        }


# ============================================================================
# Main Service
# ============================================================================

class MeasurementService:
    """
    Extracts body measurements from front and side pose images.

    Pipeline:
        1. MediaPipe → 2D keypoints from image
        2. SMPL optimization → fit body shape betas to keypoints
        3. SMPL mesh → anthropometric measurements

    Drop-in replacement for the old MediaPipe-only service.
    Same method signature, same return format.
    """

    def __init__(self):
        self.backend_mode = (settings.REGRESSOR_BACKEND or "local_smpl").strip().lower()
        if self.backend_mode == "shapy":
            self.backend_mode = "shapy_remote"
        if self.backend_mode not in {"local_smpl", "shapy_remote"}:
            logger.warning(
                f"Unknown REGRESSOR_BACKEND='{self.backend_mode}', using local_smpl"
            )
            self.backend_mode = "local_smpl"
        self.shapy_client = SHAPYClient(
            base_url=settings.SHAPY_SERVICE_URL,
            timeout=settings.SHAPY_TIMEOUT,
            api_key=settings.SHAPY_API_KEY,
        )
        self.pose_detector = PoseDetector()
        self.shape_fitter = SMPLShapeFitter()
        self.measurer = SMPLMeasurer()
        logger.info(
            "MeasurementService initialized "
            f"(device={DEVICE}, backend_mode={self.backend_mode})"
        )

    async def extract_measurements(
        self,
        front_image: bytes,
        side_image: bytes,
        height_cm: float,
        weight_kg: float,
        gender: str,
    ) -> Dict:
        """
        Main extraction method — matches the API contract exactly.

        Args:
            front_image: Front pose image bytes (JPEG/PNG)
            side_image: Side pose image bytes (JPEG/PNG)
            height_cm: User's height in centimeters
            weight_kg: User's weight in kilograms
            gender: "male", "female", or "unisex"

        Returns:
            {
                "measurements": { ... 15 measurements ... },
                "body_type": str,
                "confidence_score": float,
                "missing_measurements": [],
                "missing_reason": None or str
            }
        """
        if self.backend_mode == "shapy_remote":
            try:
                shapy_result = await self.shapy_client.measure(
                    front_image=front_image,
                    side_image=side_image,
                    height_cm=height_cm,
                    weight_kg=weight_kg,
                    gender=gender,
                )
                logger.info("Measurements extracted via SHAPY remote service")
                return shapy_result
            except SHAPYServiceUnavailableError as exc:
                logger.warning(
                    f"SHAPY unavailable, falling back to local SMPL pipeline: {exc}"
                )
            except SHAPYClientError as exc:
                logger.warning(
                    f"SHAPY response/client error, falling back to local SMPL pipeline: {exc}"
                )
            except Exception as exc:
                logger.warning(
                    f"Unexpected SHAPY error, falling back to local SMPL pipeline: {exc}"
                )

        return self._extract_local_smpl(
            front_image=front_image,
            side_image=side_image,
            height_cm=height_cm,
            weight_kg=weight_kg,
            gender=gender,
        )

    def _extract_local_smpl(
        self,
        front_image: bytes,
        side_image: bytes,
        height_cm: float,
        weight_kg: float,
        gender: str,
    ) -> Dict:
        smpl_gender = "neutral" if gender == "unisex" else gender

        # ----- Stage 1: Detect pose from front image -----
        front_pose = self.pose_detector.detect(front_image)
        if front_pose is None:
            raise ValueError(
                "Could not detect a person in the front image. "
                "Please ensure full body is visible."
            )

        # Optionally detect side pose too
        side_pose = self.pose_detector.detect(side_image)
        if side_pose is None:
            logger.warning("Could not detect pose in side image, using front only")

        # ----- Stage 2: Fit SMPL shape to keypoints -----
        front_betas, front_conf = self.shape_fitter.fit(
            landmarks_2d=front_pose["landmarks"],
            image_shape=front_pose["image_shape"],
            gender=smpl_gender,
            height_cm=height_cm,
        )

        if side_pose is not None:
            try:
                side_betas, side_conf = self.shape_fitter.fit(
                    landmarks_2d=side_pose["landmarks"],
                    image_shape=side_pose["image_shape"],
                    gender=smpl_gender,
                    height_cm=height_cm,
                )
                # Weighted average
                betas = 0.6 * front_betas + 0.4 * side_betas
                confidence = 0.6 * front_conf + 0.4 * side_conf
            except Exception as e:
                logger.warning(f"Side image fitting failed ({e}), using front only")
                betas = front_betas
                confidence = front_conf
        else:
            betas = front_betas
            confidence = front_conf

        # ----- Stage 3: Extract measurements from SMPL mesh -----
        measurements = self.measurer.measure(
            betas=betas,
            gender=smpl_gender,
            height_cm=height_cm,
        )

        # ----- Check for missing measurements -----
        all_expected = [
            "height", "shoulder_width", "arm_length", "torso_length",
            "inseam", "chest", "waist", "hip", "neck", "thigh",
            "upper_arm", "wrist", "calf", "ankle", "bicep",
        ]

        missing_measurements = []
        for name in all_expected:
            if measurements.get(name) is None:
                missing_measurements.append(name)

        missing_reason = None
        if missing_measurements:
            missing_reason = (
                "Some measurements could not be computed from the "
                "reconstructed 3D body model. This may happen with "
                "unusual poses or partially visible bodies."
            )

        # ----- Classify body type -----
        body_type = self._classify_body_type(
            measurements, weight_kg, height_cm
        )

        # Adjust confidence for completeness
        completeness = 1.0 - (len(missing_measurements) / len(all_expected))
        final_confidence = round(confidence * completeness, 2)

        return {
            "measurements": measurements,
            "body_type": body_type,
            "confidence_score": final_confidence,
            "missing_measurements": missing_measurements,
            "missing_reason": missing_reason,
        }

    def _classify_body_type(
        self, measurements: Dict, weight_kg: float, height_cm: float
    ) -> str:
        """Classify body type based on BMI and proportions."""
        height_m = height_cm / 100
        bmi = weight_kg / (height_m ** 2)

        if bmi < 18.5:
            return "slim"
        elif bmi < 25:
            chest = measurements.get("chest") or 0
            waist = measurements.get("waist") or 0
            if chest > 0 and waist > 0 and (chest / waist) > 1.25:
                return "athletic"
            return "average"
        elif bmi < 30:
            chest = measurements.get("chest") or 0
            waist = measurements.get("waist") or 0
            if chest > 0 and waist > 0 and (chest / waist) > 1.15:
                return "athletic"
            return "average"
        else:
            return "heavy"
