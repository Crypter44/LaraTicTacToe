"""Capture photos from the Intel RealSense D405 through the normal macOS camera interface (OpenCV).

    python camera.py                  # one photo -> captures/<time>.png
    python camera.py --name board     # one photo -> captures/board_<time>.png
    python camera.py --index 1        # if the RealSense is not found automatically

In code:

    with Camera() as camera:
        image = camera.capture()      # numpy array, height x width x 3, BGR (OpenCV's colour order)

Over a USB 2.0 cable the D405 gives at most 1280 x 720 at 5 frames per second.
"""

import argparse
from datetime import datetime
from pathlib import Path
from typing import Self

import cv2
import numpy as np

WIDTH, HEIGHT = 1280, 720
CAPTURES = Path(__file__).parent / "captures"

REALSENSE_DEFAULT_WIDTH = 640  # the D405 opens at 640 x 480, the Mac's webcam at 1920 x 1080
MAX_CAMERA_INDEX = 4
WARMUP_FRAMES = 10             # auto exposure needs a few frames to settle after opening
STALE_FRAMES = 2               # frames the driver may still hold from before capture() was called


def find_realsense_index() -> int:
    """macOS numbers cameras in no fixed order, so look for the one that opens at the D405's default width."""
    for index in range(MAX_CAMERA_INDEX):
        capture = cv2.VideoCapture(index, cv2.CAP_AVFOUNDATION)
        found = capture.isOpened() and capture.get(cv2.CAP_PROP_FRAME_WIDTH) == REALSENSE_DEFAULT_WIDTH
        capture.release()
        if found:
            return index
    raise RuntimeError("RealSense not found: is it plugged in, and may this app use the camera?")


class Camera:
    def __init__(self, index: int | None = None, width: int = WIDTH, height: int = HEIGHT):
        self.width, self.height = width, height
        self.index = find_realsense_index() if index is None else index
        self._capture = cv2.VideoCapture(self.index, cv2.CAP_AVFOUNDATION)
        if not self._capture.isOpened():
            raise RuntimeError(f"cannot open camera {self.index}")
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self._read_frames(WARMUP_FRAMES)

    def capture(self) -> np.ndarray:
        """A fresh frame (BGR), taken after this call, not one the driver buffered earlier."""
        self._read_frames(STALE_FRAMES)
        ok, image = self._capture.read()
        if not ok:
            raise RuntimeError("camera returned no frame")
        if image.shape[:2] != (self.height, self.width):
            # the camera silently falls back to another size if it does not support the requested one
            raise RuntimeError(f"got {image.shape[1]}x{image.shape[0]}, expected {self.width}x{self.height}")
        return image

    def close(self) -> None:
        self._capture.release()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _read_frames(self, count: int) -> None:
        for _ in range(count):
            self._capture.read()


def save(image: np.ndarray, name: str = "", folder: Path = CAPTURES) -> Path:
    """Save as captures/<name>_<time>.png and return the path."""
    folder.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = folder / (f"{name}_{stamp}.png" if name else f"{stamp}.png")
    cv2.imwrite(str(path), image)
    return path


def main():
    parser = argparse.ArgumentParser(description="Capture one photo with the RealSense.")
    parser.add_argument("--name", default="", help="prefix of the file name")
    parser.add_argument("--index", type=int, help="camera index, found automatically if left out")
    args = parser.parse_args()

    with Camera(args.index) as camera:
        print(f"camera {camera.index}, {camera.width}x{camera.height}")
        path = save(camera.capture(), args.name)
    print("saved", path)


if __name__ == "__main__":
    main()
