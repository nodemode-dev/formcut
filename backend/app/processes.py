import subprocess
import time


def communicate(process, data=None, timeout=600, cancelled=lambda: False):
    deadline = time.monotonic() + timeout
    first = True
    try:
        while True:
            if cancelled():
                raise InterruptedError("Cancelled")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Local processing timed out")
            try:
                return process.communicate(data if first else None, timeout=min(0.25, remaining))
            except subprocess.TimeoutExpired:
                first = False
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()
