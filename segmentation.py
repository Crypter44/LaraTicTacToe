"""Cut a photo of the board into the 9 cell images (issue #3).

    python segmentation.py --calibrate captures/board_<time>.png   # once: click the 4 grid crossings
    python segmentation.py captures/board_<time>.png               # -> captures/board_<time>_cells/cell_0..8.png
    python segmentation.py captures/board_<time>.png --color       # keep the colours (default: black and white)

The photo must come from the camera pose (BoardDrawer.go_to_camera_pose, `c` in main.py), so the board always
sits at the same place in the image. Calibration: click the 4 crossings of the drawn grid lines, in this order:

        0 | 1 | 2          1st crossing: between cells 0, 1, 3, 4
       ---A---B---         2nd crossing: between cells 1, 2, 4, 5   (A = 1st, B = 2nd)
        3 | 4 | 5          3rd crossing: between cells 4, 5, 7, 8   (C = 3rd, D = 4th)
       ---D---C---         4th crossing: between cells 3, 4, 6, 7
        6 | 7 | 8

The crossings are saved to camera_crossings.json and stay valid as long as the camera pose and the board
don't move. They define a perspective transform to a straight top view, in which every cell is a square.
"""

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

CROSSINGS_FILE = Path(__file__).parent / "camera_crossings.json"
CELL_PX = 200        # side of one cell in the straightened top view
MARGIN = 0.12        # fraction of a cell cut away on each side, so the grid lines are not in the cell images

# Black and white: the photos are dark, bluish and lit unevenly (darker corners), and the pen is often faint.
BACKGROUND_BLUR = 51   # px, median blur much wider than a pen line: leaves only the board and its lighting
SMOOTH = 5             # px, Gaussian blur against the board's fine texture before thresholding
INK_DARKNESS = 0.94    # a pixel darker than this fraction of the board around it counts as pen
MIN_BLOB_AREA = 60     # px, smaller dark specks are dirt or noise, not pen
CROSSING_NAMES = ["between cells 0, 1, 3, 4", "between cells 1, 2, 4, 5",
                  "between cells 4, 5, 7, 8", "between cells 3, 4, 6, 7"]
# where the 4 crossings lie in the top view, in cell units: the inner square of the 3 x 3 board
CROSSINGS_IN_TOP_VIEW = [(1, 1), (2, 1), (2, 2), (1, 2)]


def click_crossings(image: np.ndarray) -> list[tuple[int, int]]:
    """Show the image and let the user click the 4 grid crossings in CROSSING_NAMES order. Esc aborts."""
    clicks = []
    window = "click the grid crossings (Esc = abort)"

    def on_mouse(event, x, y, *_):
        if event == cv2.EVENT_LBUTTONDOWN and len(clicks) < 4:
            clicks.append((x, y))

    cv2.namedWindow(window)
    cv2.setMouseCallback(window, on_mouse)
    while len(clicks) < 4:
        shown = image.copy()
        for i, point in enumerate(clicks):
            cv2.circle(shown, point, 6, (0, 0, 255), 2)
            cv2.putText(shown, str(i + 1), (point[0] + 8, point[1] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        cv2.putText(shown, f"click crossing {len(clicks) + 1}: {CROSSING_NAMES[len(clicks)]}", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
        cv2.imshow(window, shown)
        if cv2.waitKey(30) == 27:  # Esc
            break
    cv2.destroyWindow(window)
    if len(clicks) < 4:
        raise SystemExit("aborted, nothing saved")
    return clicks


def save_crossings(crossings: list[tuple[int, int]]) -> None:
    CROSSINGS_FILE.write_text(json.dumps(crossings))


def load_crossings() -> list[tuple[int, int]]:
    return [tuple(point) for point in json.loads(CROSSINGS_FILE.read_text())]


def top_view(image: np.ndarray, crossings: list[tuple[int, int]]) -> np.ndarray:
    """The board straightened into a square of 3 x 3 cells of CELL_PX each, cell 0 at the top left."""
    source = np.float32(crossings)
    target = np.float32([(col * CELL_PX, row * CELL_PX) for col, row in CROSSINGS_IN_TOP_VIEW])
    transform = cv2.getPerspectiveTransform(source, target)
    # parts of the board outside the photo are filled with the photo's edge colour, not black
    return cv2.warpPerspective(image, transform, (3 * CELL_PX, 3 * CELL_PX), borderMode=cv2.BORDER_REPLICATE)


def to_black_and_white(image: np.ndarray) -> np.ndarray:
    """White board, black pen: one channel, 255 = board, 0 = pen."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # dividing by the blurred board removes the uneven lighting: the board becomes ~255 everywhere
    flat = cv2.divide(gray, cv2.medianBlur(gray, BACKGROUND_BLUR), scale=255)
    smooth = cv2.GaussianBlur(flat, (SMOOTH, SMOOTH), 0)
    ink = (smooth < INK_DARKNESS * 255).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    blobs = [i for i in range(1, count) if stats[i, cv2.CC_STAT_AREA] >= MIN_BLOB_AREA]  # label 0 = board
    return np.where(np.isin(labels, blobs), 0, 255).astype(np.uint8)


def split_cells(image: np.ndarray, crossings: list[tuple[int, int]],
                black_and_white: bool = True) -> list[np.ndarray]:
    """The 9 cell images, list index = cell number, each without the grid lines around it.
    With `black_and_white` the board is white and the pen black (see to_black_and_white)."""
    view = top_view(image, crossings)
    if black_and_white:
        view = to_black_and_white(view)  # on the whole top view, so the lighting is estimated over a large area
    margin = int(MARGIN * CELL_PX)
    cells = []
    for cell in range(9):
        row, col = divmod(cell, 3)
        top, left = row * CELL_PX + margin, col * CELL_PX + margin
        cells.append(view[top:top + CELL_PX - 2 * margin, left:left + CELL_PX - 2 * margin])
    return cells


def save_cells(cells: list[np.ndarray], folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    for cell, image in enumerate(cells):
        cv2.imwrite(str(folder / f"cell_{cell}.png"), image)
    return folder


def cells_folder(photo: Path) -> Path:
    """captures/board_<time>.png -> captures/board_<time>_cells/"""
    return photo.with_name(photo.stem + "_cells")


def main():
    parser = argparse.ArgumentParser(description="Cut a board photo into the 9 cell images.")
    parser.add_argument("photo", type=Path, help="photo taken from the camera pose")
    parser.add_argument("--calibrate", action="store_true", help="click the 4 grid crossings and save them first")
    parser.add_argument("--color", action="store_true", help="keep the colours instead of black and white")
    args = parser.parse_args()

    image = cv2.imread(str(args.photo))
    if image is None:
        raise SystemExit(f"cannot read {args.photo}")
    if args.calibrate:
        save_crossings(click_crossings(image))
        print("saved", CROSSINGS_FILE)
    crossings = load_crossings()
    folder = save_cells(split_cells(image, crossings, black_and_white=not args.color), cells_folder(args.photo))
    view = top_view(image, crossings)
    cv2.imwrite(str(folder / "top_view.png"), view if args.color else to_black_and_white(view))
    print("cells and top view saved to", folder)


if __name__ == "__main__":
    main()
