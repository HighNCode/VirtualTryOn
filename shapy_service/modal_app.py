import modal


app = modal.App("virtual-tryon-shapy")

image = (
    # Use CUDA devel image so mesh-mesh-intersection CUDA extension can compile.
    modal.Image.from_registry(
        "nvidia/cuda:11.7.1-cudnn8-devel-ubuntu20.04",
        add_python="3.10",
    )
    .env(
        {
            "DEBIAN_FRONTEND": "noninteractive",
            "TZ": "Etc/UTC",
            "CUDA_HOME": "/usr/local/cuda",
            "FORCE_CUDA": "1",
            "TORCH_CUDA_ARCH_LIST": "7.5;8.6",
            "MEDIAPIPE_DISABLE_GPU": "1",
            "PYOPENGL_PLATFORM": "egl",
            "PYGLET_HEADLESS": "true",
        }
    )
    .apt_install(
        "git",
        "python3.8",
        "python3.8-dev",
        "python3.8-venv",
        "build-essential",
        "ninja-build",
        "libgl1",
        "libglib2.0-0",
        "libusb-1.0-0",
        "libegl1",
        "libegl-mesa0",
        "libgles2",
        "libx11-6",
        "libxext6",
        "libxrender1",
        "libxrandr2",
        "libxi6",
        "libxinerama1",
        "libsm6",
        "libice6",
        "libturbojpeg",
    )
    .run_commands("python -m pip install --upgrade pip setuptools wheel")
    .add_local_file("main.py", "/root/service/main.py", copy=True)
    .add_local_file("measurement_mapper.py", "/root/service/measurement_mapper.py", copy=True)
    .add_local_file("shapy_wrapper.py", "/root/service/shapy_wrapper.py", copy=True)
    .add_local_file("shapy_measurement_runner.py", "/root/service/shapy_measurement_runner.py", copy=True)
    .add_local_file("requirements.txt", "/root/service/requirements.txt", copy=True)
    .add_local_dir("measurement_engine", remote_path="/root/service/measurement_engine", copy=True)
    .add_local_dir("../backend/libs/smpl_anthropometry", remote_path="/root/service/smpl_anthropometry", copy=True)
    .add_local_dir("shapy", remote_path="/root/shapy", copy=True)
    .add_local_dir("../backend/data", remote_path="/root/data", copy=True)
    .run_commands("bash -lc \"rm -rf /root/shapy/data && ln -s /root/data /root/shapy/data\"")
    .run_commands("python -m pip install -r /root/service/requirements.txt")
    .run_commands("python3.8 -m venv /opt/shapy38")
    .run_commands("/opt/shapy38/bin/python -m pip install --upgrade pip setuptools wheel")
    .run_commands(
        "/opt/shapy38/bin/python -m pip install --no-cache-dir torch==1.13.1+cu117 torchvision==0.14.1+cu117 "
        "-f https://download.pytorch.org/whl/torch_stable.html"
    )
    .run_commands(
        "bash -lc \"grep -vE '^(torch|torchvision)==.*$|^chumpy==.*$' /root/shapy/requirements.txt > /tmp/shapy_requirements_filtered.txt\""
    )
    .run_commands("/opt/shapy38/bin/python -m pip install -r /tmp/shapy_requirements_filtered.txt")
    .run_commands("/opt/shapy38/bin/python -m pip install shapely==1.8.5.post1")
    .run_commands("/opt/shapy38/bin/python -m pip install -e /root/shapy/attributes")
    .run_commands("/opt/shapy38/bin/python -m pip install /root/shapy/mesh-mesh-intersection")
    .env(
        {
            "PYTHONPATH": "/root/shapy/regressor:/root/shapy/mesh-mesh-intersection:/root/service:/root/service/smpl_anthropometry",
            "SHAPY_REPO_DIR": "/root/shapy",
            "SHAPY_DATA_DIR": "/root/data",
            "SHAPY_CHECKPOINT": "/root/data/trained_models/shapy/SHAPY_A/checkpoints/best_checkpoint",
            "SHAPY_PYTHON": "/opt/shapy38/bin/python",
            "SMPL_ANTHROPOMETRY_PATH": "/root/service/smpl_anthropometry",
        }
    )
)


@app.function(
    image=image,
    gpu="L4",
    timeout=60 * 10,
    scaledown_window=60 * 5,
)
@modal.asgi_app()
def fastapi_app():
    from main import app as web_app

    return web_app
