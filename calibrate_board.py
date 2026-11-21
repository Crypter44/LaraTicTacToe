"""Probe the board height on a grid and save it to board_heights.json.

    python calibrate_board.py              # 5 x 5 points over the whole board, ~10 minutes
    python calibrate_board.py --points 3   # 3 x 3 points, quicker

Before running: jog the pen 6-10 mm ABOVE the centre of the board (not touching). The script probes from
the centre outwards. Each descent starts APPROACH above the nearest point already measured, so a tilted or
warped board is followed. Between points the pen moves TRAVEL_LIFT above the start height with move_linear.
Keep the E-stop within reach: if anything moves unexpectedly, press it.
"""

import argparse
import math
from pathlib import Path

from neurapy.robot import Robot

from board_drawer import CELL_SIZE
from height_map import HeightMap, board_to_base
from probing import Prober

HOST = "192.168.2.13"
OUTPUT = Path(__file__).parent / "board_heights.json"

HALF_SIZE = 1.5 * CELL_SIZE  # m from the board centre to its edge
BOARD_ROTATION = 45.0        # degrees the board edges are turned against the robot's x/y axes (a diamond)
TRAVEL_LIFT = 0.015          # m above the start height while moving between points
TRAVEL_SPEED = 0.02          # m/s
APPROACH = 0.008             # m above the nearest measured height where the next descent starts (the torque
                             # may need up to 6 s = 3 mm to settle before contact detection starts)


def connect() -> Robot:
    robot = Robot(HOST)
    robot.switch_to_real()
    robot.switch_to_automatic_mode()
    robot.set_override(1.0)
    if robot.is_robot_in_simulation():
        raise RuntimeError("robot is still in simulation, calibration needs the real board")
    return robot


def grid_offsets(points: int) -> list[float]:
    """Evenly spaced offsets from the board centre to both edges, along one board edge."""
    step = 2 * HALF_SIZE / (points - 1)
    return [-HALF_SIZE + i * step for i in range(points)]


def centre_outwards(us: list[float], vs: list[float]) -> list[tuple[int, int]]:
    """All (row, col) grid indices, nearest to the centre first, so every point has a measured neighbour."""
    cells = [(row, col) for row in range(len(vs)) for col in range(len(us))]
    return sorted(cells, key=lambda rc: math.hypot(us[rc[1]], vs[rc[0]]))


def nearest_measured_z(measured: dict, u: float, v: float) -> float | None:
    """Height of the measured point closest to board position (u, v), None if nothing is measured yet."""
    if not measured:
        return None
    closest = min(measured, key=lambda uv: math.hypot(uv[0] - u, uv[1] - v))
    return measured[closest]


def move_to(robot: Robot, pose: list[float]) -> None:
    robot.move_linear(target_pose=[pose], speed=TRAVEL_SPEED, acceleration=0.1, enable_safety=True)


def travel(robot: Robot, center_euler: list[float], x: float, y: float, travel_z: float, start_z: float) -> None:
    """Straight up to the travel height, across to (x, y), down to the probe start height."""
    current = robot.get_tcp_pose()
    move_to(robot, [current[0], current[1], travel_z, *center_euler[3:]])
    move_to(robot, [x, y, travel_z, *center_euler[3:]])
    move_to(robot, [x, y, start_z, *center_euler[3:]])


def print_map(heights: HeightMap) -> None:
    """Heights in mm relative to the centre value, along the board edges, top row (largest v) first."""
    reference = heights.z_at(heights.center_pose[0], heights.center_pose[1])
    print(f"\nheight relative to the board centre [mm], rows along the board edges "
          f"(turned {heights.rotation_deg:.0f}° against the robot axes), top row = +v:")
    for row in reversed(heights.z):
        print("  " + " ".join(f"{(z - reference) * 1000:+6.2f}" for z in row))


def main():
    parser = argparse.ArgumentParser(description="Probe the board height on a grid.")
    parser.add_argument("--points", type=int, default=5, help="grid points per side (default 5)")
    parser.add_argument("--rotation", type=float, default=BOARD_ROTATION,
                        help=f"degrees the board is turned against the robot axes (default {BOARD_ROTATION:.0f})")
    parser.add_argument("--out", type=Path, default=OUTPUT)
    args = parser.parse_args()

    if input(f"REAL arm will probe {args.points}x{args.points} points over ±{HALF_SIZE * 1000:.0f} mm, "
             f"turned {args.rotation:.0f}°. Pen 6-10 mm above the board centre? Type 'yes': ") != "yes":
        print("aborted")
        return

    robot = connect()
    center_euler = robot.get_tcp_pose()            # for move_linear
    center_quat = robot.get_tcp_pose_quaternion()  # for movelinear_online, same position
    hover_z = center_euler[2]
    travel_z = hover_z + TRAVEL_LIFT
    us = vs = grid_offsets(args.points)
    prober = Prober(robot)
    measured = {}  # board (u, v) -> contact z

    try:
        order = centre_outwards(us, vs)
        for n, (row, col) in enumerate(order, 1):
            u, v = us[col], vs[row]
            x, y = board_to_base(center_euler, args.rotation, u, v)
            neighbour_z = nearest_measured_z(measured, u, v)
            start_z = hover_z if neighbour_z is None else neighbour_z + APPROACH
            travel(robot, center_euler, x, y, travel_z, start_z)
            contact_z = prober.probe([x, y, start_z, *center_quat[3:]])
            measured[(u, v)] = contact_z
            print(f"[{n:2d}/{len(order)}] u {u * 1000:+5.0f} mm  v {v * 1000:+5.0f} mm  "
                  f"board z {contact_z * 1000:7.2f} mm")
    finally:
        # back above the board centre; the servo interface is already off here, so move_linear is safe
        travel(robot, center_euler, *center_euler[:2], travel_z, hover_z)
        robot.stop()

    heights = HeightMap(us, vs, [[measured[(u, v)] for u in us] for v in vs], center_euler, args.rotation)
    heights.save(args.out)
    print_map(heights)
    print("saved", args.out)


if __name__ == "__main__":
    main()
