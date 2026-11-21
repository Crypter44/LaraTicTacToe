"""Draw one straight line and record the arm's actual path, to see where and how it deviates (issue #2).

    python tests/stroke_test.py --real --offset 3                 # in the air, one single move (default)
    python tests/stroke_test.py --real --offset 3 --segment 20    # waypoints every 20 mm, blended
    python tests/stroke_test.py --real --offset 3 --lead-in 20    # 20 mm run-up in the air first
    python tests/stroke_test.py --real --offset 3 --speed 10      # half speed: is the unsteady part shorter?

The line runs through the board centre along the first board edge, LINE_HALF_LENGTH to each side. While the
arm moves, a background thread reads the TCP pose as fast as it can. The table shows, every BIN mm along the
line, how far the pen was off in height (against the planned height) and sideways. Negative distances are
the run-up. If the unsteady part stays ~2 cm long at half speed, it comes from the path (first segment); if it
gets ~1 cm long, it is a time effect (joint friction, ~1 s). Logs go to logs/stroke_<time>.csv.
"""

import argparse
import csv
import statistics
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Self

import board_drawer
from board_drawer import (
    DRAW_OFFSET,
    LEAD_IN,
    LEAD_IN_HEIGHT,
    SEGMENT_LENGTH,
    BoardDrawer,
)
from height_map import HeightMap
from main import HEIGHTS, connect

LOGS = Path(__file__).parent.parent / "logs"
LINE_HALF_LENGTH = 0.06  # m
BIN = 0.005              # m
NEAR_BOARD = 0.006       # m, samples higher than this above the planned height belong to hovering, not drawing


class PoseRecorder:
    """Reads the TCP pose in a background thread while the main thread moves the arm."""

    def __init__(self, robot):
        self.robot = robot
        self.samples = []  # (time, [x, y, z, roll, pitch, yaw])
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._record, daemon=True)

    def __enter__(self) -> Self:
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._stop.set()
        self._thread.join()

    def _record(self) -> None:
        while not self._stop.is_set():
            self.samples.append((time.perf_counter(), self.robot.get_tcp_pose()))


def planned_lift(distance: float, lead_in: float) -> float:
    """Planned pen height above the drawing height at `distance` along the line (negative = run-up)."""
    if distance >= 0 or lead_in <= 0:
        return 0.0
    return LEAD_IN_HEIGHT * min(1.0, -distance / lead_in)  # straight ramp down to the line start


def analyse(samples: list, heights: HeightMap, offset: float, lead_in: float) -> list[tuple]:
    """Rows (t, distance along the line, height error, sideways error) for samples near the board."""
    rows, t0 = [], samples[0][0]
    for t, pose in samples:
        u, v = heights.to_board(pose[0], pose[1])
        distance = u + LINE_HALF_LENGTH
        above = pose[2] - (heights.z_at(pose[0], pose[1]) + offset)
        height_error = above - planned_lift(distance, lead_in)
        if above < NEAR_BOARD and -lead_in - BIN <= distance <= 2 * LINE_HALF_LENGTH + BIN:
            rows.append((t - t0, distance, height_error, v))
    return rows


def print_table(rows: list[tuple]) -> None:
    print(f"\n{'mm along line':>14s} {'height error mm':>16s} {'max |height| mm':>16s} {'sideways mm':>12s} {'n':>4s}")
    start = min(r[1] for r in rows)
    while start <= max(r[1] for r in rows):
        binned = [r for r in rows if start <= r[1] < start + BIN]
        if binned:
            heights_mm = [r[2] * 1000 for r in binned]
            print(f"{start * 1000:6.0f} .. {(start + BIN) * 1000:4.0f} {statistics.mean(heights_mm):16.2f} "
                  f"{max(abs(h) for h in heights_mm):16.2f} {statistics.mean(r[3] * 1000 for r in binned):12.2f} "
                  f"{len(binned):4d}")
        start += BIN


def save_log(rows: list[tuple]) -> Path:
    LOGS.mkdir(exist_ok=True)
    path = LOGS / f"stroke_{datetime.now():%Y%m%d_%H%M%S}.csv"
    with path.open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["t", "distance_along_line", "height_error", "sideways_error"])
        writer.writerows(rows)
    return path


def main():
    parser = argparse.ArgumentParser(description="Draw one line and record how the arm actually moves.")
    parser.add_argument("--real", action="store_true", help="move the real arm instead of the simulation")
    parser.add_argument("--offset", type=float, default=DRAW_OFFSET * 1000, help="mm above the probed height")
    parser.add_argument("--lead-in", type=float, default=LEAD_IN * 1000, help="mm run-up in the air, 0 = off")
    parser.add_argument("--segment", type=float, default=SEGMENT_LENGTH * 1000,
                        help="mm between blended waypoints along the line, 0 = one single move")
    parser.add_argument("--speed", type=float, default=board_drawer.SPEED * 1000, help="drawing speed in mm/s")
    args = parser.parse_args()

    heights = HeightMap.load(HEIGHTS)
    if args.real and input(f"REAL arm draws a {2 * LINE_HALF_LENGTH * 1000:.0f} mm line through the board "
                           f"centre, pen {args.offset:+.1f} mm. Type 'yes': ") != "yes":
        print("aborted")
        return

    board_drawer.SPEED = args.speed / 1000  # BoardDrawer reads this module constant on every move
    robot = connect(args.real)
    drawer = BoardDrawer(robot, heights, offset=args.offset / 1000, lead_in=args.lead_in / 1000,
                         segment_length=args.segment / 1000)
    line = [(-LINE_HALF_LENGTH, 0.0), (LINE_HALF_LENGTH, 0.0)]
    try:
        drawer.park()
        with PoseRecorder(robot) as recorder:
            drawer.draw_stroke(line)
        drawer.park()
    finally:
        robot.stop()

    rows = analyse(recorder.samples, heights, args.offset / 1000, args.lead_in / 1000)
    print(f"{len(recorder.samples)} poses recorded "
          f"({len(recorder.samples) / (recorder.samples[-1][0] - recorder.samples[0][0]):.0f} per s), "
          f"{len(rows)} near the board")
    print_table(rows)
    print("log:", save_log(rows))


if __name__ == "__main__":
    main()
