import os
import subprocess
import sys
import venv
from pathlib import Path


def main():
    dotenv = Path(__file__).resolve().parent.parent / ".env"
    if dotenv.is_file():
        for line in dotenv.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.strip().partition("=")
            if sep and key.strip() == "FORMCUT_DATA_DIR":
                os.environ["FORMCUT_DATA_DIR"] = value.strip().strip("\"'")
    from app.paths import DATA_DIR

    root = DATA_DIR / "ai-runtime"
    python = root / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    if python.is_file():
        probe = subprocess.run([str(python), "-c", "import kokoro_onnx"], capture_output=True, text=True)
        if probe.returncode == 0:
            print("Local speech runtime already installed at " + str(python))
            return
    venv.EnvBuilder(with_pip=True).create(root)
    subprocess.run([str(python), "-m", "pip", "install", "kokoro-onnx==0.6.1"], check=True)
    print("Local speech runtime installed at " + str(python))
    print("Open FormCut Local models and download Kokoro, or import the two model files.")


if __name__ == "__main__":
    main()
