"""Isolated legacy smoke: no music-provider network and no changes to legacy files."""

import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


def main():
    root = Path(__file__).resolve().parents[1]
    subprocess.run([sys.executable, "server.py", "--help"], cwd=root, check=True,
                   stdout=subprocess.DEVNULL)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    process = subprocess.Popen([sys.executable, "server.py", "--port", str(port)], cwd=root,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("Legacy server exited before startup")
            try:
                with urlopen(f"http://127.0.0.1:{port}/", timeout=1) as response:
                    assert response.status == 200 and b"<html" in response.read().lower()
                print("Legacy help + isolated homepage HTTP 200: passed")
                return
            except URLError:
                time.sleep(0.1)
        raise RuntimeError("Legacy startup timed out")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


if __name__ == "__main__":
    main()
