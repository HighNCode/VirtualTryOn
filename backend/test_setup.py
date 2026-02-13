"""Quick verification that all dependencies are properly installed."""
import sys
import os

def check(name, import_fn):
    try:
        import_fn()
        print(f"  ✅ {name}")
        return True
    except Exception as e:
        print(f"  ❌ {name}: {e}")
        return False

print("Checking dependencies...\n")

all_ok = True

all_ok &= check("torch", lambda: __import__("torch"))
all_ok &= check("smplx", lambda: __import__("smplx"))
all_ok &= check("trimesh", lambda: __import__("trimesh"))
all_ok &= check("cv2", lambda: __import__("cv2"))
all_ok &= check("numpy", lambda: __import__("numpy"))
all_ok &= check("PIL", lambda: __import__("PIL"))

# Check SMPL-Anthropometry (from submodule)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "libs", "smpl_anthropometry"))
all_ok &= check("SMPL-Anthropometry (measure)", lambda: __import__("measure"))
all_ok &= check("SMPL-Anthropometry (measurement_definitions)",
                 lambda: __import__("measurement_definitions"))

# Check HMR2
all_ok &= check("HMR 2.0 (hmr2)", lambda: __import__("hmr2"))

# Check SMPL model files
print("\nChecking model files...\n")
model_dir = os.environ.get("SMPL_MODEL_DIR", "data/body_models")
for gender in ["MALE", "FEMALE", "NEUTRAL"]:
    path = os.path.join(model_dir, "smpl", f"SMPL_{gender}.pkl")
    if os.path.exists(path):
        size_mb = os.path.getsize(path) / (1024 * 1024)
        print(f"  ✅ SMPL_{gender}.pkl ({size_mb:.1f} MB)")
    else:
        print(f"  ❌ SMPL_{gender}.pkl not found at {path}")
        all_ok = False

print()
if all_ok:
    print("🎉 All checks passed! You're ready to go.")
else:
    print("⚠️  Some checks failed. See above for details.")