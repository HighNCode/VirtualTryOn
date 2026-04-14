import argparse
import json
import os
import sys

from measurement_engine import compute_measurements_from_npz


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--npz", required=True)
    parser.add_argument("--height-cm", type=float, required=True)
    parser.add_argument("--calibration-path", default=os.environ.get("SHAPY_CALIBRATION_PATH", ""))
    args = parser.parse_args()

    result = compute_measurements_from_npz(
        npz_path=args.npz,
        height_cm=args.height_cm,
        calibration_path=args.calibration_path or None,
    )
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
