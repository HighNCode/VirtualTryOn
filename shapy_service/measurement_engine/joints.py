from typing import Dict, Iterable, List

import numpy as np


def normalize_keypoint_names(raw_names: Iterable) -> List[str]:
    names: List[str] = []
    for name in raw_names:
        if isinstance(name, bytes):
            names.append(name.decode("utf-8"))
        else:
            names.append(str(name))
    return names


def build_joint_index(keypoint_names: Iterable[str]) -> Dict[str, int]:
    return {name: idx for idx, name in enumerate(keypoint_names)}


def validate_required_joints(index_by_name: Dict[str, int], required: Iterable[str]) -> List[str]:
    missing = [name for name in required if name not in index_by_name]
    return missing


def joint(joints_xyz: np.ndarray, index_by_name: Dict[str, int], name: str) -> np.ndarray:
    return joints_xyz[index_by_name[name]]
