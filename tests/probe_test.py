"""Probe the same point several times to check that contact detection works and repeats.

    python tests/probe_test.py --repeat 3
    python tests/probe_test.py --threshold 8   # less sensitive
    python tests/probe_test.py --joint 2       # watch the shoulder instead of the default joint

Before running: jog the pen 6-10 mm ABOVE the board (not touching). Every run first moves 3 mm above the
start and back down onto it, so the joint friction is loaded downwards like in calibrate_board.py, then
probes with probing.Prober. Logs go to logs/probe_<time>.csv. Keep the E-stop within reach.
"""

import argparse
import csv
import statistics
from datetime import datetime
from pathlib import Path

from neurapy.robot import Robot

from probing import SIGNAL_JOINT, THRESHOLD, Prober

HOST = "192.168.2.13"
LOGS = Path(__file__).parent.parent / "logs"  # logs/ in the project folder
PRELOAD_LIFT = 0.003   # m above the start from where each probe approaches
TRAVEL_SPEED = 0.01    # m/s for move_linear


def connect() -> Robot:
    robot = Robot(HOST)
    robot.switch_to_real()
    robot.switch_to_automatic_mode()
    robot.set_override(1.0)
    if robot.is_robot_in_simulation():
        raise RuntimeError("robot is still in simulation, the probe needs the real board")
    return robot


def move_to(robot: Robot, pose: list[float]) -> None:
    robot.move_linear(target_pose=[pose], speed=TRAVEL_SPEED, acceleration=0.1, enable_safety=True)


def approach_from_above(robot: Robot, start_euler: list[float]) -> None:
    """Go PRELOAD_LIFT above the start, then down onto it, so the last motion before probing is downwards."""
    move_to(robot, [*start_euler[:2], start_euler[2] + PRELOAD_LIFT, *start_euler[3:]])
    move_to(robot, start_euler)


def save_log(rows: list) -> Path:
    LOGS.mkdir(exist_ok=True)
    path = LOGS / f"probe_{datetime.now():%Y%m%d_%H%M%S}.csv"
    with path.open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["t", "z", "signal_torque", "deviation", "phase", *(f"tau{j}" for j in range(1, 7))])
        writer.writerows(rows)
    return path


def print_run(prober: Prober, start_z: float, contact_z: float) -> None:
    settled = next((row[0] for row in prober.log if row[4] == "baseline"), None)  # row: t, z, torque, dev, phase
    settled_text = f"torque settled after {settled:.1f} s, " if settled is not None else ""
    print(f"  {settled_text}CONTACT {(start_z - contact_z) * 1000:.2f} mm below the start")


def main():
    parser = argparse.ArgumentParser(description="Probe the same point several times.")
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--threshold", type=float, default=THRESHOLD, help="Nm that count as contact")
    parser.add_argument("--joint", type=int, default=SIGNAL_JOINT + 1, choices=range(1, 7),
                        help=f"joint (1-6) whose torque signals contact, default {SIGNAL_JOINT + 1}")
    args = parser.parse_args()

    if input("REAL arm will probe down at 0.5 mm/s. Pen 6-10 mm above the board? Type 'yes': ") != "yes":
        print("aborted")
        return

    robot = connect()
    start_euler = robot.get_tcp_pose()            # for move_linear
    start = robot.get_tcp_pose_quaternion()      # for the online probe, same position
    prober = Prober(robot, args.threshold, joint=args.joint - 1)
    contacts = []
    try:
        for run in range(1, args.repeat + 1):
            print(f"run {run}/{args.repeat}")
            approach_from_above(robot, start_euler)
            try:
                contacts.append(prober.probe(start))
                print_run(prober, start[2], contacts[-1])
            finally:
                print("  log:", save_log(prober.log))
    finally:
        move_to(robot, start_euler)  # the Prober has switched the servo interface off, so this is safe
        robot.stop()

    if len(contacts) > 1:
        depths = [(start[2] - z) * 1000 for z in contacts]
        print(f"\nmm below start: {', '.join(f'{d:.2f}' for d in depths)}")
        print(f"spread {max(depths) - min(depths):.2f} mm, std {statistics.pstdev(depths):.2f} mm")


if __name__ == "__main__":
    main()
