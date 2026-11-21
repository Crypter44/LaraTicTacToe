"""Check whether the LARA reports a TCP force when someone pushes on the pen. Read-only, never moves the arm.

    python force_test.py              # 3 s untouched, then 12 s for pushing
    python force_test.py --push 20    # longer pushing phase

While it runs, one person pushes firmly on the pen / flange a few times (from different directions),
with pauses in between. The script prints the readings live and a summary at the end, and saves
everything to logs/force_test_<time>.csv.
"""

import argparse
import csv
import statistics
import time
from datetime import datetime
from pathlib import Path

from neurapy.robot import Robot

HOST = "192.168.2.13"
REST_SECONDS = 3.0
PRINT_EVERY = 0.2  # s between live lines
LOGS = Path(__file__).parent.parent / "logs"  # logs/ in the project folder


def record(robot: Robot, seconds: float, phase: str) -> list[dict]:
    """Read TCP force and joint torques as fast as possible for `seconds`, printing a line now and then."""
    rows, start, last_print = [], time.perf_counter(), 0.0
    while (t := time.perf_counter() - start) < seconds:
        force = robot.get_tcp_force()
        torques = robot.get_current_joint_torques()
        rows.append({"phase": phase, "t": t, "force": force, "torques": torques})
        if t - last_print >= PRINT_EVERY:
            last_print = t
            print(f"  {phase:4s} {t:5.1f}s  F = {format_values(force, 6.2)} N   "
                  f"torques = {format_values(torques, 7.2)} Nm")
    return rows


def format_values(values: list[float], fmt: float) -> str:
    return " ".join(f"{v:{fmt}f}" for v in values)


def summarize(rows: list[dict]) -> None:
    """Spread of each value in the rest phase vs. the largest deviation from the rest mean while pushing."""
    rest = [r for r in rows if r["phase"] == "rest"]
    push = [r for r in rows if r["phase"] == "push"]
    print(f"\n{len(rows)} samples, {len(rows) / (rest[-1]['t'] + push[-1]['t']):.0f} per second")
    print(f"{'value':10s} {'rest mean':>10s} {'rest std':>9s} {'max push dev':>13s}")
    for key, label in (("force", "F"), ("torques", "joint")):
        for i in range(len(rows[0][key])):
            rest_values = [r[key][i] for r in rest]
            mean = statistics.mean(rest_values)
            std = statistics.pstdev(rest_values)
            deviation = max(abs(r[key][i] - mean) for r in push)
            name = f"{label}{'xyz'[i]}" if key == "force" else f"{label} {i + 1}"
            print(f"{name:10s} {mean:10.3f} {std:9.3f} {deviation:13.3f}")
    forces = {tuple(r["force"]) for r in rows}
    print("\nTCP force changed during the test" if len(forces) > 1
          else "\nTCP force never changed: the robot does not compute it")


def save_csv(rows: list[dict]) -> Path:
    LOGS.mkdir(exist_ok=True)
    path = LOGS / f"force_test_{datetime.now():%Y%m%d_%H%M%S}.csv"
    with path.open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["phase", "t", "Fx", "Fy", "Fz", *(f"tau{j}" for j in range(1, 7))])
        for r in rows:
            writer.writerow([r["phase"], f"{r['t']:.4f}", *r["force"], *r["torques"]])
    return path


def main():
    parser = argparse.ArgumentParser(description="Read-only test: does the TCP force react to pushing?")
    parser.add_argument("--push", type=float, default=12.0, help="seconds of the pushing phase")
    args = parser.parse_args()

    robot = Robot(HOST)
    print("simulation:", robot.is_robot_in_simulation())  # must be False, the sim arm cannot be pushed

    input(f"Nobody touches the arm for {REST_SECONDS:.0f} s. Press Enter to start.")
    rows = record(robot, REST_SECONDS, "rest")
    print(f"\n>>> PUSH NOW: press firmly on the pen a few times, with pauses, for {args.push:.0f} s <<<\n")
    rows += record(robot, args.push, "push")
    print("\n>>> STOP PUSHING <<<")

    summarize(rows)
    print("saved", save_csv(rows))


if __name__ == "__main__":
    main()
