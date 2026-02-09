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
from typing import Dict, List, Tuple

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
    ) -> Dict:
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
                "issues": List[str],
                "confidence": str
            }
        """
        issues = []

        # 1. Check file format and resolution
        try:
            img = Image.open(BytesIO(image_data))
            width, height = img.size
        except Exception as e:
            logger.error(f"Invalid image format: {e}")
            return {
                "valid": False,
                "is_person": False,
                "pose_detected": False,
                "pose_accuracy": 0.0,
                "issues": ["Invalid image format"],
                "confidence": "low"
            }

        # 2. Check resolution
        if width < 640 or height < 480:
            issues.append(f"Image resolution too low ({width}x{height}). Minimum 640x480 required.")

        # 3. Check file size
        if len(image_data) > 10 * 1024 * 1024:  # 10MB
            issues.append("File size exceeds 10MB limit")

        # 4. Check lighting quality
        img_array = np.array(img.convert('L'))
        mean_brightness = np.mean(img_array)

        if mean_brightness < 50:
            issues.append("Image is too dark. Please ensure good lighting.")
        elif mean_brightness > 200:
            issues.append("Image is overexposed. Please reduce lighting.")

        # 5. Detect person using MediaPipe
        img_rgb = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        img_rgb = cv2.cvtColor(img_rgb, cv2.COLOR_BGR2RGB)

        results = self.pose_detector.process(img_rgb)

        if not results.pose_landmarks:
            return {
                "valid": False,
                "is_person": False,
                "pose_detected": False,
                "pose_accuracy": 0.0,
                "issues": issues + ["No person detected in image"],
                "confidence": "low"
            }

        # 6. Validate pose based on type
        landmarks = results.pose_landmarks.landmark
        pose_accuracy = self._validate_pose_type(landmarks, pose_type, issues)

        # 7. Determine overall validity
        valid = len(issues) == 0 and pose_accuracy > 0.7

        confidence = "high" if pose_accuracy > 0.85 else "medium" if pose_accuracy > 0.7 else "low"

        return {
            "valid": valid,
            "is_person": True,
            "pose_detected": True,
            "pose_accuracy": round(pose_accuracy, 2),
            "issues": issues,
            "confidence": confidence
        }

    def _validate_pose_type(
        self,
        landmarks: List,
        pose_type: str,
        issues: List[str]
    ) -> float:
        """
        Validate pose based on front or side orientation

        Args:
            landmarks: MediaPipe pose landmarks
            pose_type: 'front' or 'side'
            issues: List to append issues to

        Returns:
            Pose accuracy score (0-1)
        """
        accuracy = 1.0

        if pose_type == "front":
            # Check if front-facing
            left_shoulder = landmarks[self.mp_pose.PoseLandmark.LEFT_SHOULDER.value]
            right_shoulder = landmarks[self.mp_pose.PoseLandmark.RIGHT_SHOULDER.value]

            # Shoulders should be approximately level
            shoulder_diff = abs(left_shoulder.y - right_shoulder.y)
            if shoulder_diff > 0.1:  # More than 10% difference
                issues.append("Please stand straight with level shoulders")
                accuracy *= 0.8

            # Both arms should be visible
            left_wrist = landmarks[self.mp_pose.PoseLandmark.LEFT_WRIST.value]
            right_wrist = landmarks[self.mp_pose.PoseLandmark.RIGHT_WRIST.value]

            if left_wrist.visibility < 0.5 or right_wrist.visibility < 0.5:
                issues.append("Please keep both arms visible and slightly away from body")
                accuracy *= 0.9

            # Check if person is facing camera (both shoulders visible)
            if left_shoulder.visibility < 0.6 or right_shoulder.visibility < 0.6:
                issues.append("Please face the camera directly")
                accuracy *= 0.7

        elif pose_type == "side":
            # Check if side profile
            # In side pose, one shoulder should be much more visible than the other
            left_shoulder = landmarks[self.mp_pose.PoseLandmark.LEFT_SHOULDER.value]
            right_shoulder = landmarks[self.mp_pose.PoseLandmark.RIGHT_SHOULDER.value]

            visibility_diff = abs(left_shoulder.visibility - right_shoulder.visibility)

            if visibility_diff < 0.3:
                issues.append("Please stand in a clear side profile")
                accuracy *= 0.7

            # Check if body is vertical (not leaning)
            nose = landmarks[self.mp_pose.PoseLandmark.NOSE.value]
            left_hip = landmarks[self.mp_pose.PoseLandmark.LEFT_HIP.value]
            right_hip = landmarks[self.mp_pose.PoseLandmark.RIGHT_HIP.value]

            avg_hip_y = (left_hip.y + right_hip.y) / 2
            vertical_diff = abs(nose.x - (left_hip.x + right_hip.x) / 2)

            if vertical_diff > 0.15:
                issues.append("Please stand straight without leaning")
                accuracy *= 0.9

        return accuracy

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
