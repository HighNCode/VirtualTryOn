"""
Image Validation Service
Validates image quality and pose accuracy using MediaPipe
"""

from io import BytesIO
from PIL import Image
import cv2
import numpy as np
import mediapipe as mp
import logging
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


class ImageValidator:
    """Validates images for measurement extraction"""

    def __init__(self):
        # Initialize MediaPipe Pose
        self.mp_pose = mp.solutions.pose
        self.pose_detector = self.mp_pose.Pose(
            static_image_mode=True,
            model_complexity=2,
            min_detection_confidence=0.5
        )

    async def validate_image(
        self,
        image_data: bytes,
        pose_type: str
    ) -> Dict[str, Any]:
        """
        Comprehensive image validation

        Args:
            image_data: Image bytes
            pose_type: 'front' or 'side'

        Returns:
            {
                "valid": bool,
                "is_person": bool,
                "pose_detected": bool,
                "pose_accuracy": float,
                "issues": List[str],  # Backward-compatible list of messages
                "confidence": str
            }
        """
        warnings: List[Dict[str, Any]] = []
        hard_failures: List[Dict[str, Any]] = []
        metrics: Dict[str, Any] = {
            "file_size_bytes": int(len(image_data)),
            "pose_type": pose_type,
        }

        # 1. Check file format and resolution
        try:
            img = Image.open(BytesIO(image_data))
            width, height = img.size
            metrics["width"] = int(width)
            metrics["height"] = int(height)
        except Exception as e:
            logger.error(f"Invalid image format: {e}")
            self._add_reason(
                hard_failures,
                code="INVALID_IMAGE_FORMAT",
                message="The uploaded file is not a valid image.",
                observed={"error": str(e)},
                expected="A valid JPEG/PNG photo",
                suggestion="Upload a clear photo in JPG or PNG format.",
            )
            return self._build_result(False, False, warnings, hard_failures, 0.0, metrics)

        # 2. Check resolution
        if width < 480 or height < 360:
            self._add_reason(
                hard_failures,
                code="LOW_RESOLUTION",
                message="Image resolution is too low for reliable pose detection.",
                observed={"width": int(width), "height": int(height)},
                expected={"min_width": 480, "min_height": 360},
                suggestion="Move farther from camera and capture at a higher resolution.",
            )
        elif width < 640 or height < 480:
            self._add_reason(
                warnings,
                code="LOW_RESOLUTION",
                message="Image resolution is lower than recommended and may reduce measurement accuracy.",
                observed={"width": int(width), "height": int(height)},
                expected={"recommended_width": 640, "recommended_height": 480},
                suggestion="Use a slightly higher-resolution photo for better fit accuracy.",
            )

        # 3. Check file size
        if len(image_data) > 10 * 1024 * 1024:  # 10MB
            self._add_reason(
                hard_failures,
                code="FILE_TOO_LARGE",
                message="File size exceeds the 10MB limit.",
                observed={"file_size_bytes": int(len(image_data))},
                expected={"max_file_size_bytes": 10 * 1024 * 1024},
                suggestion="Compress the photo or export at a smaller size and retry.",
            )

        # 4. Check lighting quality
        img_array = np.array(img.convert('L'))
        mean_brightness = np.mean(img_array)
        metrics["mean_brightness"] = round(float(mean_brightness), 2)

        if mean_brightness < 30:
            self._add_reason(
                hard_failures,
                code="TOO_DARK",
                message="Image is too dark to reliably detect body landmarks.",
                observed={"mean_brightness": round(float(mean_brightness), 2)},
                expected={"min_mean_brightness": 30},
                suggestion="Increase room lighting and avoid backlighting behind you.",
            )
        elif mean_brightness < 45:
            self._add_reason(
                warnings,
                code="TOO_DARK",
                message="Image is somewhat dark and may reduce pose quality.",
                observed={"mean_brightness": round(float(mean_brightness), 2)},
                expected={"recommended_min_mean_brightness": 45},
                suggestion="Use brighter lighting for better measurement quality.",
            )
        elif mean_brightness > 235:
            self._add_reason(
                hard_failures,
                code="OVEREXPOSED",
                message="Image is overexposed and body edges are not reliable.",
                observed={"mean_brightness": round(float(mean_brightness), 2)},
                expected={"max_mean_brightness": 235},
                suggestion="Reduce direct light or move away from very bright background.",
            )
        elif mean_brightness > 210:
            self._add_reason(
                warnings,
                code="OVEREXPOSED",
                message="Image is bright and may reduce landmark precision.",
                observed={"mean_brightness": round(float(mean_brightness), 2)},
                expected={"recommended_max_mean_brightness": 210},
                suggestion="Try softer or indirect lighting.",
            )

        # 5. Detect person using MediaPipe
        img_rgb = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        img_rgb = cv2.cvtColor(img_rgb, cv2.COLOR_BGR2RGB)

        results = self.pose_detector.process(img_rgb)

        if not results.pose_landmarks:
            self._add_reason(
                hard_failures,
                code="NO_PERSON_DETECTED",
                message="No clear full-body person was detected in the image.",
                observed={"pose_landmarks_detected": False},
                expected="Single visible full-body person",
                suggestion="Step back so your full body is in frame and retake the photo.",
            )
            return self._build_result(False, False, warnings, hard_failures, 0.0, metrics)

        # 6. Validate pose based on type
        landmarks = results.pose_landmarks.landmark
        key_visibility = self._extract_key_visibility(landmarks)
        metrics["key_landmark_visibility"] = key_visibility

        self._validate_critical_landmarks(key_visibility, warnings, hard_failures)
        orientation_metrics = self._validate_pose_type(landmarks, pose_type, warnings, hard_failures)
        metrics["orientation_metrics"] = orientation_metrics

        # 7. Compute score + final status (hard failures reject, warnings do not)
        pose_accuracy = max(0.0, min(1.0, 1.0 - (0.08 * len(warnings)) - (0.22 * len(hard_failures))))
        return self._build_result(True, True, warnings, hard_failures, pose_accuracy, metrics)

    def _validate_pose_type(
        self,
        landmarks: List,
        pose_type: str,
        warnings: List[Dict[str, Any]],
        hard_failures: List[Dict[str, Any]],
    ) -> Dict[str, float]:
        """
        Validate pose based on front or side orientation

        Args:
            landmarks: MediaPipe pose landmarks
            pose_type: 'front' or 'side'
            warnings: Warning reasons list
            hard_failures: Hard-failure reasons list

        Returns:
            Orientation metrics dictionary
        """
        left_shoulder = landmarks[self.mp_pose.PoseLandmark.LEFT_SHOULDER.value]
        right_shoulder = landmarks[self.mp_pose.PoseLandmark.RIGHT_SHOULDER.value]
        left_hip = landmarks[self.mp_pose.PoseLandmark.LEFT_HIP.value]
        right_hip = landmarks[self.mp_pose.PoseLandmark.RIGHT_HIP.value]
        left_wrist = landmarks[self.mp_pose.PoseLandmark.LEFT_WRIST.value]
        right_wrist = landmarks[self.mp_pose.PoseLandmark.RIGHT_WRIST.value]
        nose = landmarks[self.mp_pose.PoseLandmark.NOSE.value]
        left_ankle = landmarks[self.mp_pose.PoseLandmark.LEFT_ANKLE.value]
        right_ankle = landmarks[self.mp_pose.PoseLandmark.RIGHT_ANKLE.value]

        shoulder_diff_y = abs(left_shoulder.y - right_shoulder.y)
        shoulder_span = abs(left_shoulder.x - right_shoulder.x)
        hip_span = abs(left_hip.x - right_hip.x)
        shoulder_vis_diff = abs(left_shoulder.visibility - right_shoulder.visibility)
        hip_vis_diff = abs(left_hip.visibility - right_hip.visibility)
        hip_mid_x = (left_hip.x + right_hip.x) / 2
        shoulder_mid_x = (left_shoulder.x + right_shoulder.x) / 2
        ankle_mid_x = (left_ankle.x + right_ankle.x) / 2
        nose_to_hip_x = abs(nose.x - hip_mid_x)
        torso_center_offset_x = abs(nose.x - shoulder_mid_x)
        lean_offset_x = abs(shoulder_mid_x - ankle_mid_x)

        orientation_metrics = {
            "shoulder_diff_y": round(float(shoulder_diff_y), 4),
            "shoulder_span_x": round(float(shoulder_span), 4),
            "hip_span_x": round(float(hip_span), 4),
            "shoulder_visibility_diff": round(float(shoulder_vis_diff), 4),
            "hip_visibility_diff": round(float(hip_vis_diff), 4),
            "nose_to_hip_mid_x": round(float(nose_to_hip_x), 4),
            "torso_center_offset_x": round(float(torso_center_offset_x), 4),
            "lean_offset_x": round(float(lean_offset_x), 4),
            "left_wrist_visibility": round(float(left_wrist.visibility), 4),
            "right_wrist_visibility": round(float(right_wrist.visibility), 4),
        }

        if pose_type == "front":
            if shoulder_span < 0.06 or hip_span < 0.05:
                self._add_reason(
                    hard_failures,
                    code="FRONT_ORIENTATION_UNCLEAR",
                    message="Front pose appears too narrow; body seems turned or too far from camera.",
                    observed={"shoulder_span_x": orientation_metrics["shoulder_span_x"], "hip_span_x": orientation_metrics["hip_span_x"]},
                    expected={"min_shoulder_span_x": 0.06, "min_hip_span_x": 0.05},
                    suggestion="Face the camera directly and keep your full body clearly visible.",
                )
            elif shoulder_span < 0.08 or hip_span < 0.07:
                self._add_reason(
                    warnings,
                    code="FRONT_ORIENTATION_UNCLEAR",
                    message="Front pose is slightly narrow and may reduce accuracy.",
                    observed={"shoulder_span_x": orientation_metrics["shoulder_span_x"], "hip_span_x": orientation_metrics["hip_span_x"]},
                    expected={"recommended_shoulder_span_x": 0.08, "recommended_hip_span_x": 0.07},
                    suggestion="Stand a bit closer and keep your torso fully facing the camera.",
                )

            if shoulder_diff_y > 0.2:
                self._add_reason(
                    hard_failures,
                    code="FRONT_ALIGNMENT_OFF",
                    message="Shoulders are strongly tilted for front pose.",
                    observed={"shoulder_diff_y": orientation_metrics["shoulder_diff_y"]},
                    expected={"max_shoulder_diff_y": 0.2},
                    suggestion="Stand straight and keep both shoulders level.",
                )
            elif shoulder_diff_y > 0.12:
                self._add_reason(
                    warnings,
                    code="FRONT_ALIGNMENT_OFF",
                    message="Shoulders are slightly tilted.",
                    observed={"shoulder_diff_y": orientation_metrics["shoulder_diff_y"]},
                    expected={"recommended_max_shoulder_diff_y": 0.12},
                    suggestion="Stand upright with relaxed and level shoulders.",
                )

            min_wrist_visibility = min(left_wrist.visibility, right_wrist.visibility)
            if min_wrist_visibility < 0.18:
                self._add_reason(
                    hard_failures,
                    code="FRONT_ARMS_OCCLUDED",
                    message="Arms are not visible enough for front pose.",
                    observed={"left_wrist_visibility": orientation_metrics["left_wrist_visibility"], "right_wrist_visibility": orientation_metrics["right_wrist_visibility"]},
                    expected={"min_wrist_visibility": 0.18},
                    suggestion="Keep both arms visible and slightly away from your torso.",
                )
            elif min_wrist_visibility < 0.42:
                self._add_reason(
                    warnings,
                    code="FRONT_ARMS_OCCLUDED",
                    message="Arms are partly occluded and may reduce quality.",
                    observed={"left_wrist_visibility": orientation_metrics["left_wrist_visibility"], "right_wrist_visibility": orientation_metrics["right_wrist_visibility"]},
                    expected={"recommended_min_wrist_visibility": 0.42},
                    suggestion="Let your arms hang naturally with a small gap from body.",
                )

            if torso_center_offset_x > 0.24:
                self._add_reason(
                    hard_failures,
                    code="FRONT_NOT_CENTERED",
                    message="Body alignment suggests the front pose is not straight-on.",
                    observed={"torso_center_offset_x": orientation_metrics["torso_center_offset_x"]},
                    expected={"max_torso_center_offset_x": 0.24},
                    suggestion="Face forward and keep your body square to the camera.",
                )
            elif torso_center_offset_x > 0.16:
                self._add_reason(
                    warnings,
                    code="FRONT_NOT_CENTERED",
                    message="Body is slightly rotated relative to camera.",
                    observed={"torso_center_offset_x": orientation_metrics["torso_center_offset_x"]},
                    expected={"recommended_max_torso_center_offset_x": 0.16},
                    suggestion="Rotate slightly to face the camera more directly.",
                )

        elif pose_type == "side":
            # Side profile check focuses on body-width contraction + asymmetry cues,
            # instead of relying on visibility difference alone.
            if shoulder_span > 0.28 and hip_span > 0.24:
                self._add_reason(
                    hard_failures,
                    code="SIDE_PROFILE_UNCLEAR",
                    message="Pose appears too front-facing for side profile.",
                    observed={"shoulder_span_x": orientation_metrics["shoulder_span_x"], "hip_span_x": orientation_metrics["hip_span_x"]},
                    expected={"max_shoulder_span_x": 0.28, "max_hip_span_x": 0.24},
                    suggestion="Turn your body sideways (left or right profile).",
                )
            elif shoulder_span > 0.22 or hip_span > 0.19:
                self._add_reason(
                    warnings,
                    code="SIDE_PROFILE_UNCLEAR",
                    message="Side profile is not very clear and may lower accuracy.",
                    observed={"shoulder_span_x": orientation_metrics["shoulder_span_x"], "hip_span_x": orientation_metrics["hip_span_x"]},
                    expected={"recommended_max_shoulder_span_x": 0.22, "recommended_max_hip_span_x": 0.19},
                    suggestion="Turn a bit more sideways for a cleaner profile.",
                )

            if shoulder_vis_diff < 0.04 and shoulder_span > 0.24:
                self._add_reason(
                    hard_failures,
                    code="SIDE_PROFILE_UNCLEAR",
                    message="Shoulder cues indicate near-front orientation, not side profile.",
                    observed={"shoulder_visibility_diff": orientation_metrics["shoulder_visibility_diff"], "shoulder_span_x": orientation_metrics["shoulder_span_x"]},
                    expected={"min_shoulder_visibility_diff_for_wide_span": 0.04},
                    suggestion="Rotate your body further to side profile.",
                )
            elif shoulder_vis_diff < 0.1:
                self._add_reason(
                    warnings,
                    code="SIDE_PROFILE_UNCLEAR",
                    message="Shoulder depth/asymmetry cues are weak for side profile.",
                    observed={"shoulder_visibility_diff": orientation_metrics["shoulder_visibility_diff"]},
                    expected={"recommended_min_shoulder_visibility_diff": 0.1},
                    suggestion="Slightly rotate more to one side.",
                )

            if lean_offset_x > 0.16:
                self._add_reason(
                    hard_failures,
                    code="BODY_LEANING",
                    message="Body appears strongly leaned; vertical alignment is unreliable.",
                    observed={"lean_offset_x": orientation_metrics["lean_offset_x"]},
                    expected={"max_lean_offset_x": 0.16},
                    suggestion="Stand naturally upright with feet flat and body relaxed.",
                )
            elif lean_offset_x > 0.1:
                self._add_reason(
                    warnings,
                    code="BODY_LEANING",
                    message="Slight body lean detected.",
                    observed={"lean_offset_x": orientation_metrics["lean_offset_x"]},
                    expected={"recommended_max_lean_offset_x": 0.1},
                    suggestion="Stand a little straighter before retaking.",
                )

            if nose_to_hip_x < 0.02:
                self._add_reason(
                    warnings,
                    code="SIDE_HEAD_ALIGNMENT_WEAK",
                    message="Head position provides weak side-profile cue.",
                    observed={"nose_to_hip_mid_x": orientation_metrics["nose_to_hip_mid_x"]},
                    expected={"recommended_min_nose_to_hip_mid_x": 0.02},
                    suggestion="Keep your head naturally aligned with side profile.",
                )
        else:
            self._add_reason(
                hard_failures,
                code="INVALID_POSE_TYPE",
                message="Pose type must be either front or side.",
                observed={"pose_type": pose_type},
                expected=["front", "side"],
                suggestion="Retry with a valid pose type.",
            )

        return orientation_metrics

    def _extract_key_visibility(self, landmarks: List) -> Dict[str, float]:
        def vis(name: str) -> float:
            idx = self.mp_pose.PoseLandmark[name].value
            return round(float(landmarks[idx].visibility), 4)

        return {
            "left_shoulder": vis("LEFT_SHOULDER"),
            "right_shoulder": vis("RIGHT_SHOULDER"),
            "left_hip": vis("LEFT_HIP"),
            "right_hip": vis("RIGHT_HIP"),
            "left_knee": vis("LEFT_KNEE"),
            "right_knee": vis("RIGHT_KNEE"),
            "left_ankle": vis("LEFT_ANKLE"),
            "right_ankle": vis("RIGHT_ANKLE"),
            "left_wrist": vis("LEFT_WRIST"),
            "right_wrist": vis("RIGHT_WRIST"),
            "nose": vis("NOSE"),
        }

    def _validate_critical_landmarks(
        self,
        key_visibility: Dict[str, float],
        warnings: List[Dict[str, Any]],
        hard_failures: List[Dict[str, Any]],
    ) -> None:
        critical_keys = [
            "left_shoulder", "right_shoulder", "left_hip", "right_hip",
            "left_ankle", "right_ankle",
        ]
        critical_values = [key_visibility[k] for k in critical_keys]
        min_critical = min(critical_values)
        avg_critical = float(np.mean(critical_values))

        if min_critical < 0.15 or avg_critical < 0.28:
            self._add_reason(
                hard_failures,
                code="KEY_LANDMARKS_MISSING",
                message="Critical body landmarks are not visible enough.",
                observed={
                    "min_critical_visibility": round(min_critical, 4),
                    "avg_critical_visibility": round(avg_critical, 4),
                    "critical_visibility": {k: key_visibility[k] for k in critical_keys},
                },
                expected={"min_critical_visibility": 0.15, "avg_critical_visibility": 0.28},
                suggestion="Keep full body in frame and avoid objects covering shoulders/hips/feet.",
            )
        elif min_critical < 0.25 or avg_critical < 0.4:
            self._add_reason(
                warnings,
                code="KEY_LANDMARKS_WEAK",
                message="Some key landmarks are weakly visible and may reduce precision.",
                observed={
                    "min_critical_visibility": round(min_critical, 4),
                    "avg_critical_visibility": round(avg_critical, 4),
                },
                expected={"recommended_min_critical_visibility": 0.25, "recommended_avg_critical_visibility": 0.4},
                suggestion="Ensure your full body is clearly visible with some space around you.",
            )

    def _add_reason(
        self,
        target: List[Dict[str, Any]],
        *,
        code: str,
        message: str,
        observed: Any,
        expected: Any,
        suggestion: str,
    ) -> None:
        target.append(
            {
                "code": code,
                "message": message,
                "observed": observed,
                "expected": expected,
                "suggestion": suggestion,
            }
        )

    def _build_result(
        self,
        is_person: bool,
        pose_detected: bool,
        warnings: List[Dict[str, Any]],
        hard_failures: List[Dict[str, Any]],
        pose_accuracy: float,
        metrics: Dict[str, Any],
    ) -> Dict[str, Any]:
        if hard_failures:
            status = "rejected"
            confidence = "low"
        elif warnings:
            status = "accepted_with_warnings"
            confidence = "medium" if pose_accuracy >= 0.75 else "low"
        else:
            status = "accepted"
            confidence = "high" if pose_accuracy >= 0.85 else "medium"

        issues = [r["message"] for r in hard_failures] + [r["message"] for r in warnings]

        return {
            "valid": status != "rejected",  # Backward-compat contract
            "status": status,
            "is_person": is_person,
            "pose_detected": pose_detected,
            "pose_accuracy": round(float(pose_accuracy), 2),
            "issues": issues,
            "warnings": warnings,
            "hard_failures": hard_failures,
            "metrics": metrics,
            "confidence": confidence,
        }

    def get_pose_landmarks(self, image_data: bytes) -> Tuple[bool, List]:
        """
        Extract pose landmarks from image

        Args:
            image_data: Image bytes

        Returns:
            (success, landmarks)
        """
        try:
            img = Image.open(BytesIO(image_data))
            img_rgb = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            img_rgb = cv2.cvtColor(img_rgb, cv2.COLOR_BGR2RGB)

            results = self.pose_detector.process(img_rgb)

            if results.pose_landmarks:
                return True, results.pose_landmarks.landmark

            return False, []

        except Exception as e:
            logger.error(f"Pose landmark extraction failed: {e}")
            return False, []

    def __del__(self):
        """Cleanup MediaPipe resources"""
        if hasattr(self, 'pose_detector'):
            self.pose_detector.close()
