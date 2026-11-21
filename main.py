"""Draw X and O on a tic-tac-toe board with the LARA 5, one move at a time.

    python main.py                          # in the simulation
    python main.py --real                   # on the real arm, asks for confirmation first
    python main.py --real --offset 0.3      # pen 0.3 mm above the probed height instead of the default

Needs board_heights.json from calibrate_board.py (run it again whenever the board moves).
Commands: `g` draws the grid, `x 4` / `o 0` a symbol in a cell (0-8, see board_drawer.py), `c` moves to the
camera pose, takes a photo and cuts it into the 9 cells (see segmentation.py), `q` quits.
Keep the E-stop within reach.
"""

import argparse
from pathlib import Path

# neurapy lives in vendor/, which .venv/lib/python3.13/site-packages/vendor.pth puts on the import path
from neurapy.robot import Robot

import segmentation
from board_drawer import DRAW_OFFSET, BoardDrawer
from camera import Camera, save
from height_map import HeightMap

HOST = "192.168.2.13"
HEIGHTS = Path(__file__).parent / "board_heights.json"


def connect(real: bool) -> Robot:
    robot = Robot(HOST)
    if real:
        robot.switch_to_real()
    else:
        robot.switch_to_simulation()
    robot.switch_to_automatic_mode()  # the robot only accepts move commands in automatic mode
    robot.set_override(1.0)           # run at 100 % of the programmed speeds
    return robot


def ask_command() -> list[str] | None:
    """Ask until the input is 'g', 'c' or a valid move like 'x 4'. None means quit."""
    while True:
        text = input("command ('g' = grid, 'x 4' / 'o 0' = symbol, 'c' = capture, q = quit): ").strip().lower()
        if text == "q":
            return None
        parts = text.split()
        if parts in (["g"], ["c"]):
            return parts
        if len(parts) == 2 and parts[0] in ("x", "o") and parts[1] in list("012345678"):
            return parts
        print("  invalid, expected g, c, or x / o followed by a cell 0-8")


def capture_board(drawer: BoardDrawer) -> None:
    """Move to the camera pose, take a photo and, once the grid crossings are calibrated, cut it into cells."""
    drawer.go_to_camera_pose()
    with Camera() as camera:
        image = camera.capture()
    photo = save(image, "board")
    print("photo:", photo)
    if not segmentation.CROSSINGS_FILE.exists():
        print(f"  no {segmentation.CROSSINGS_FILE.name} yet: python segmentation.py --calibrate {photo}")
        return
    cells = segmentation.split_cells(image, segmentation.load_crossings())
    print("cells:", segmentation.save_cells(cells, segmentation.cells_folder(photo)))


def run_command(drawer: BoardDrawer, command: list[str]) -> None:
    if command == ["g"]:
        drawer.draw_grid()
    elif command == ["c"]:
        capture_board(drawer)
    else:
        symbol, cell = command
        drawer.draw(symbol, int(cell))


def main():
    parser = argparse.ArgumentParser(description="Draw X and O on a tic-tac-toe board.")
    parser.add_argument("--real", action="store_true", help="move the real arm instead of the simulation")
    parser.add_argument("--offset", type=float, default=DRAW_OFFSET * 1000,
                        help=f"mm above the probed board height while drawing (default {DRAW_OFFSET * 1000})")
    args = parser.parse_args()

    heights = HeightMap.load(HEIGHTS)
    print(f"board centre {[round(v, 4) for v in heights.center_pose[:3]]}, turned {heights.rotation_deg:.0f}°, "
          f"pen {args.offset:+.1f} mm above the probed height")
    if args.real and input("REAL arm will draw on the board. Type 'yes': ") != "yes":
        print("aborted")
        return

    robot = connect(args.real)
    drawer = BoardDrawer(robot, heights, offset=args.offset / 1000)

    try:
        while (command := ask_command()) is not None:
            run_command(drawer, command)
    finally:
        robot.stop()


if __name__ == "__main__":
    main()
