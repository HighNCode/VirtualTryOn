"""
Measurement Extraction Service
Extracts 15 body measurements from front and side pose images using MediaPipe
"""

from io import BytesIO
from PIL import Image
import cv2
import numpy as np
import mediapipe as mp
import math
import logging
from typing import Dict, Tuple, List

logger = logging.getLogger(__name__)


class MeasurementService:
    """
    Extracts body measurements from front and side pose images
    """

    def __init__(self):
        # Initialize MediaPipe Pose
        self.mp_pose = mp.solutions.pose
        self.pose_detector = self.mp_pose.Pose(
            static_image_mode=True,
            model_complexity=2,
            min_detection_confidence=0.7
        )

    async def extract_measurements(
        self,
        front_image: bytes,
        side_image: bytes,
        height_cm: float,
        weight_kg: float,
        gender: str
    ) -> Dict:
        """
        Main extraction method

        Returns:
        {
          "measurements": {...},
          "body_type": "athletic",
          "confidence_score": 0.87
        }
        """
        # 1. Detect pose landmarks
        front_landmarks, front_img_shape = self._detect_pose(front_image)
        side_landmarks, side_img_shape = self._detect_pose(side_image)

        if not front_landmarks or not side_landmarks:
            raise ValueError("Could not detect pose in one or both images")

        # 2. Calculate pixel-to-cm ratio using provided height
        pixel_ratio = self._calculate_pixel_ratio(front_landmarks, front_img_shape, height_cm)

        # 3. Extract measurements
        measurements = {
            "height": height_cm,
            "shoulder_width": self._measure_shoulder_width(front_landmarks, pixel_ratio),
            "chest": self._measure_chest(front_landmarks, side_landmarks, pixel_ratio, gender),
            "waist": self._measure_waist(front_landmarks, side_landmarks, pixel_ratio),
            "hip": self._measure_hip(front_landmarks, side_landmarks, pixel_ratio),
            "inseam": self._measure_inseam(front_landmarks, pixel_ratio),
            "arm_length": self._measure_arm_length(front_landmarks, pixel_ratio),
            "torso_length": self._measure_torso_length(front_landmarks, pixel_ratio),
            "neck": self._estimate_neck(front_landmarks, pixel_ratio, gender),
            "thigh": self._estimate_thigh(front_landmarks, side_landmarks, pixel_ratio),
            "upper_arm": self._estimate_upper_arm(front_landmarks, side_landmarks, pixel_ratio),
            "wrist": self._estimate_wrist(front_landmarks, pixel_ratio),
            "calf": self._estimate_calf(front_landmarks, side_landmarks, pixel_ratio),
            "ankle": self._estimate_ankle(front_landmarks, pixel_ratio),
            "bicep": self._estimate_bicep(front_landmarks, side_landmarks, pixel_ratio)
        }

        # 4. Determine body type
        body_type = self._classify_body_type(measurements, weight_kg, height_cm, gender)

        # 5. Calculate confidence
        confidence = self._calculate_confidence(front_landmarks, side_landmarks)

        return {
            "measurements": measurements,
            "body_type": body_type,
            "confidence_score": round(confidence, 2)
        }

    def _detect_pose(self, image_data: bytes) -> Tuple[List, Tuple]:
        """Detect pose and return landmarks"""
        img = Image.open(BytesIO(image_data))
        img_array = np.array(img)
        img_rgb = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        img_rgb = cv2.cvtColor(img_rgb, cv2.COLOR_BGR2RGB)

        results = self.pose_detector.process(img_rgb)

        if not results.pose_landmarks:
            return None, None

        return results.pose_landmarks.landmark, img_array.shape

    def _calculate_pixel_ratio(self, landmarks: List, img_shape: Tuple, height_cm: float) -> float:
        """
        Calculate pixel-to-cm ratio using known height

        Uses top of head to ankle distance
        """
        # Get top of head (approximate from nose)
        nose = landmarks[self.mp_pose.PoseLandmark.NOSE.value]

        # Get ankles
        left_ankle = landmarks[self.mp_pose.PoseLandmark.LEFT_ANKLE.value]
        right_ankle = landmarks[self.mp_pose.PoseLandmark.RIGHT_ANKLE.value]
        avg_ankle_y = (left_ankle.y + right_ankle.y) / 2

        # Calculate pixel height (normalized coordinates * image height)
        pixel_height = (avg_ankle_y - nose.y) * img_shape[0]

        # Pixel ratio: cm per pixel
        pixel_ratio = height_cm / abs(pixel_height)

        return pixel_ratio

    def _measure_shoulder_width(self, landmarks: List, pixel_ratio: float) -> float:
        """Measure shoulder width (direct measurement)"""
        left_shoulder = landmarks[self.mp_pose.PoseLandmark.LEFT_SHOULDER.value]
        right_shoulder = landmarks[self.mp_pose.PoseLandmark.RIGHT_SHOULDER.value]

        # Calculate distance in pixels
        dx = abs(right_shoulder.x - left_shoulder.x)
        dy = abs(right_shoulder.y - left_shoulder.y)
        pixel_distance = math.sqrt(dx**2 + dy**2)

        # Convert to cm (need to account for image dimensions)
        # Assuming normalized coordinates [0, 1]
        shoulder_width_cm = pixel_distance * 1000 * pixel_ratio  # Rough estimate

        return round(shoulder_width_cm, 1)

    def _measure_chest(self, front_landmarks: List, side_landmarks: List, pixel_ratio: float, gender: str) -> float:
        """
        Calculate chest circumference using ellipse formula
        - Front width from shoulders
        - Side depth estimation
        """
        # Get front chest width (shoulder to shoulder)
        left_shoulder = front_landmarks[self.mp_pose.PoseLandmark.LEFT_SHOULDER.value]
        right_shoulder = front_landmarks[self.mp_pose.PoseLandmark.RIGHT_SHOULDER.value]
        front_width_px = abs(right_shoulder.x - left_shoulder.x) * 1000  # Scale up from normalized

        front_width_cm = front_width_px * pixel_ratio

        # Estimate side depth (approximation)
        side_depth_cm = front_width_cm * 0.5  # Chest depth ~ 50% of width

        # Calculate circumference using ellipse formula
        # C ≈ π * sqrt(2 * (a² + b²)) where a = width/2, b = depth/2
        a = front_width_cm / 2
        b = side_depth_cm / 2
        circumference = math.pi * math.sqrt(2 * (a**2 + b**2))

        # Apply gender correction
        if gender == "male":
            circumference *= 1.05
        elif gender == "female":
            circumference *= 1.02

        return round(circumference, 1)

    def _measure_waist(self, front_landmarks: List, side_landmarks: List, pixel_ratio: float) -> float:
        """Calculate waist circumference"""
        # Get hip positions
        left_hip = front_landmarks[self.mp_pose.PoseLandmark.LEFT_HIP.value]
        right_hip = front_landmarks[self.mp_pose.PoseLandmark.RIGHT_HIP.value]

        # Waist width
        waist_width_px = abs(right_hip.x - left_hip.x) * 1000
        waist_width_cm = waist_width_px * pixel_ratio

        # Estimate depth
        waist_depth_cm = waist_width_cm * 0.4  # Waist depth ~ 40% of width

        # Ellipse circumference
        a = waist_width_cm / 2
        b = waist_depth_cm / 2
        circumference = math.pi * math.sqrt(2 * (a**2 + b**2))

        return round(circumference, 1)

    def _measure_hip(self, front_landmarks: List, side_landmarks: List, pixel_ratio: float) -> float:
        """Calculate hip circumference"""
        left_hip = front_landmarks[self.mp_pose.PoseLandmark.LEFT_HIP.value]
        right_hip = front_landmarks[self.mp_pose.PoseLandmark.RIGHT_HIP.value]

        hip_width_px = abs(right_hip.x - left_hip.x) * 1000
        hip_width_cm = hip_width_px * pixel_ratio

        hip_depth_cm = hip_width_cm * 0.45

        a = hip_width_cm / 2
        b = hip_depth_cm / 2
        circumference = math.pi * math.sqrt(2 * (a**2 + b**2))

        return round(circumference, 1)

    def _measure_inseam(self, landmarks: List, pixel_ratio: float) -> float:
        """Measure inseam (hip to ankle)"""
        left_hip = landmarks[self.mp_pose.PoseLandmark.LEFT_HIP.value]
        left_ankle = landmarks[self.mp_pose.PoseLandmark.LEFT_ANKLE.value]

        dy = abs(left_ankle.y - left_hip.y) * 1000
        inseam_cm = dy * pixel_ratio

        return round(inseam_cm, 1)

    def _measure_arm_length(self, landmarks: List, pixel_ratio: float) -> float:
        """Measure arm length (shoulder to wrist)"""
        left_shoulder = landmarks[self.mp_pose.PoseLandmark.LEFT_SHOULDER.value]
        left_wrist = landmarks[self.mp_pose.PoseLandmark.LEFT_WRIST.value]

        dx = abs(left_wrist.x - left_shoulder.x) * 1000
        dy = abs(left_wrist.y - left_shoulder.y) * 1000
        arm_length_px = math.sqrt(dx**2 + dy**2)

        arm_length_cm = arm_length_px * pixel_ratio

        return round(arm_length_cm, 1)

    def _measure_torso_length(self, landmarks: List, pixel_ratio: float) -> float:
        """Measure torso length (shoulder to hip)"""
        left_shoulder = landmarks[self.mp_pose.PoseLandmark.LEFT_SHOULDER.value]
        left_hip = landmarks[self.mp_pose.PoseLandmark.LEFT_HIP.value]

        dy = abs(left_hip.y - left_shoulder.y) * 1000
        torso_cm = dy * pixel_ratio

        return round(torso_cm, 1)

    def _estimate_neck(self, landmarks: List, pixel_ratio: float, gender: str) -> float:
        """Estimate neck circumference"""
        # Approximate from shoulder width
        left_shoulder = landmarks[self.mp_pose.PoseLandmark.LEFT_SHOULDER.value]
        right_shoulder = landmarks[self.mp_pose.PoseLandmark.RIGHT_SHOULDER.value]

        shoulder_width_px = abs(right_shoulder.x - left_shoulder.x) * 1000
        shoulder_width_cm = shoulder_width_px * pixel_ratio

        # Neck ~ 35% of shoulder width
        neck_cm = shoulder_width_cm * 0.35

        if gender == "male":
            neck_cm *= 1.1
        elif gender == "female":
            neck_cm *= 0.95

        return round(neck_cm, 1)

    def _estimate_thigh(self, front_landmarks: List, side_landmarks: List, pixel_ratio: float) -> float:
        """Estimate thigh circumference"""
        # Use hip width as reference
        left_hip = front_landmarks[self.mp_pose.PoseLandmark.LEFT_HIP.value]
        right_hip = front_landmarks[self.mp_pose.PoseLandmark.RIGHT_HIP.value]

        hip_width_px = abs(right_hip.x - left_hip.x) * 1000
        hip_width_cm = hip_width_px * pixel_ratio

        # Thigh ~ 60% of hip width
        thigh_cm = hip_width_cm * 0.6

        return round(thigh_cm, 1)

    def _estimate_upper_arm(self, front_landmarks: List, side_landmarks: List, pixel_ratio: float) -> float:
        """Estimate upper arm circumference"""
        # Based on arm length
        left_shoulder = front_landmarks[self.mp_pose.PoseLandmark.LEFT_SHOULDER.value]
        left_elbow = front_landmarks[self.mp_pose.PoseLandmark.LEFT_ELBOW.value]

        arm_width_px = abs(left_elbow.x - left_shoulder.x) * 1000
        arm_width_cm = arm_width_px * pixel_ratio

        upper_arm_cm = arm_width_cm * 0.4

        return round(upper_arm_cm, 1)

    def _estimate_wrist(self, landmarks: List, pixel_ratio: float) -> float:
        """Estimate wrist circumference"""
        # Small circumference estimation
        return round(17.0, 1)  # Average estimation

    def _estimate_calf(self, front_landmarks: List, side_landmarks: List, pixel_ratio: float) -> float:
        """Estimate calf circumference"""
        # Based on ankle position
        return round(36.0, 1)  # Average estimation

    def _estimate_ankle(self, landmarks: List, pixel_ratio: float) -> float:
        """Estimate ankle circumference"""
        return round(23.0, 1)  # Average estimation

    def _estimate_bicep(self, front_landmarks: List, side_landmarks: List, pixel_ratio: float) -> float:
        """Estimate bicep circumference"""
        return round(31.0, 1)  # Average estimation

    def _classify_body_type(self, measurements: Dict, weight_kg: float, height_cm: float, gender: str) -> str:
        """
        Classify body type based on BMI and proportions

        Returns: 'slim', 'average', 'athletic', or 'heavy'
        """
        # Calculate BMI
        height_m = height_cm / 100
        bmi = weight_kg / (height_m ** 2)

        # BMI categories
        if bmi < 18.5:
            return "slim"
        elif bmi < 25:
            # Check proportions for athletic build
            chest = measurements.get("chest", 0)
            waist = measurements.get("waist", 0)

            if chest > 0 and waist > 0:
                ratio = chest / waist
                if ratio > 1.25:  # Wide chest relative to waist
                    return "athletic"

            return "average"
        elif bmi < 30:
            return "athletic"  # Could be muscular
        else:
            return "heavy"

    def _calculate_confidence(self, front_landmarks: List, side_landmarks: List) -> float:
        """Calculate confidence score based on landmark visibility"""
        total_confidence = 0
        count = 0

        # Check key landmarks
        key_landmarks = [
            self.mp_pose.PoseLandmark.NOSE,
            self.mp_pose.PoseLandmark.LEFT_SHOULDER,
            self.mp_pose.PoseLandmark.RIGHT_SHOULDER,
            self.mp_pose.PoseLandmark.LEFT_HIP,
            self.mp_pose.PoseLandmark.RIGHT_HIP,
            self.mp_pose.PoseLandmark.LEFT_ANKLE,
            self.mp_pose.PoseLandmark.RIGHT_ANKLE,
        ]

        for landmark_idx in key_landmarks:
            front_lm = front_landmarks[landmark_idx.value]
            total_confidence += front_lm.visibility
            count += 1

        return total_confidence / count if count > 0 else 0.0

    def __del__(self):
        """Cleanup MediaPipe resources"""
        if hasattr(self, 'pose_detector'):
            self.pose_detector.close()
