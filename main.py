"""Draw X and O on a tic-tac-toe board with the LARA 5, one move at a time.

    python main.py                          # in the simulation
    python main.py --real                   # on the real arm, asks for confirmation first
    python main.py --real --offset 0.3      # pen 0.3 mm above the probed height instead of the default

Needs board_heights.json from calibrate_board.py (run it again whenever the board moves).
Type `g` to draw the grid, moves like `x 5` or `o 1`, `q` to quit. Keep the E-stop within reach.
"""

import argparse
from pathlib import Path

# neurapy lives in vendor/, which .venv/lib/python3.13/site-packages/vendor.pth puts on the import path
from neurapy.robot import Robot

from board_drawer import DRAW_OFFSET, BoardDrawer
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
    """Ask until the input is 'g' or a valid move like 'x 5'. None means quit."""
    while True:
        text = input("command ('g' = grid, 'x 5' / 'o 1' = symbol, q = quit): ").strip().lower()
        if text == "q":
            return None
        parts = text.split()
        if parts == ["g"]:
            return parts
        if len(parts) == 2 and parts[0] in ("x", "o") and parts[1] in list("123456789"):
            return parts
        print("  invalid, expected g, or x / o followed by a cell 1-9")


def run_command(drawer: BoardDrawer, command: list[str]) -> None:
    if command == ["g"]:
        drawer.draw_grid()
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
