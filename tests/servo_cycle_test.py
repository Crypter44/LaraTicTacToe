"""Air test: can we switch the servo interface off, move with move_linear, and switch it back on safely?

    python tests/servo_cycle_test.py --sim       # check the calls in the simulation first
    python tests/servo_cycle_test.py --no-hold   # real arm, the old way: try to reproduce the jump
    python tests/servo_cycle_test.py             # real arm, with the "hold" fix

Background: in probe_test.py the cycle "servo off -> move_linear up -> servo on -> descend" once made the
arm jump 7 mm at ~35 mm/s to where the previous online motion had stopped. move_linear would make travel
between grid points fast, so this tests whether sending the current position as a "hold" target right after
switching the servo interface on prevents the jump.

Each cycle: servo on, (hold), online descent DROP mm, servo off, move_linear back up. Everything happens in
the air: jog the pen at least 30 mm above the board, so even a jump cannot reach it.
"""

import argparse
import time

from probe_test import (
    AT_TARGET,
    SafetyError,
    activate_servo,
    connect,
    send_target,
    shut_down,
    wait_until_still,
    with_z,
)

DROP = 0.003            # m per online descent
DESCENT_SPEED = 0.002   # m/s
RETURN_SPEED = 0.01     # m/s for move_linear
CYCLES = 10
JUMP_FACTOR = 3.0       # faster than this times the commanded speed counts as a jump
SPEED_WINDOW = 0.05     # s over which the speed is measured


def hold_current_position(robot, speed: float) -> None:
    """Send the actual position as target, so the online motion starts from where the arm really is."""
    current = robot.get_tcp_pose_quaternion()
    send_target(robot, current, speed)
    time.sleep(0.3)
    if abs(robot.get_tcp_pose_quaternion()[2] - current[2]) > AT_TARGET:
        raise SafetyError("arm moved after the hold target")


def descend(robot, start: list[float], stop_midway: bool) -> float:
    """Online descent DROP below `start`; returns the highest speed seen (m/s).
    With `stop_midway` it is interrupted at half the distance, like the probe does on contact."""
    target_z = start[2] - DROP
    start_time = time.perf_counter()
    # first sample before sending, so a jump that happens right away still shows up as speed
    samples, max_speed = [(0.0, robot.get_tcp_pose_quaternion()[2])], 0.0
    send_target(robot, with_z(start, target_z), DESCENT_SPEED)
    while (t := time.perf_counter() - start_time) < DROP / DESCENT_SPEED + 3.0:
        z = robot.get_tcp_pose_quaternion()[2]
        samples.append((t, z))
        older = [s for s in samples if t - s[0] >= SPEED_WINDOW]
        if older:
            t0, z0 = older[-1]
            max_speed = max(max_speed, abs(z - z0) / (t - t0))
        if abs(z - target_z) < AT_TARGET:
            break
        if stop_midway and start[2] - z >= DROP / 2:
            robot.stop_movelinear_online()
            break
    wait_until_still(robot)
    return max_speed


def return_with_move_linear(robot, start_euler: list[float]) -> float:
    """Servo off, then a normal move_linear back to the start. Returns the duration in s."""
    robot.stop_movelinear_online()
    robot.deactivate_servo_interface()
    start_time = time.perf_counter()
    robot.move_linear(target_pose=[start_euler], speed=RETURN_SPEED, acceleration=0.1, enable_safety=True)
    return max(time.perf_counter() - start_time, 1e-3)  # move_linear blocks until arrived; avoid / 0


def main():
    parser = argparse.ArgumentParser(description="Servo on/off cycles in the air, looking for jumps.")
    parser.add_argument("--sim", action="store_true", help="use the simulation")
    parser.add_argument("--no-hold", action="store_true", help="skip the hold target (the old, jumpy way)")
    parser.add_argument("--cycles", type=int, default=CYCLES)
    parser.add_argument("--stop-midway", action="store_true",
                        help="interrupt each descent halfway with stop_movelinear_online, like the probe on contact")
    args = parser.parse_args()

    if not args.sim and input("REAL arm, pen at least 30 mm ABOVE the board? Type 'yes': ") != "yes":
        print("aborted")
        return

    robot = connect(args.sim)
    start_euler = robot.get_tcp_pose()
    start = robot.get_tcp_pose_quaternion()
    print("start:", [round(v, 4) for v in start_euler], "| hold:", not args.no_hold)

    jumps = 0
    try:
        for cycle in range(1, args.cycles + 1):
            activate_servo(robot)
            if not args.no_hold:
                hold_current_position(robot, DESCENT_SPEED)
            max_speed = descend(robot, start, args.stop_midway)
            duration = return_with_move_linear(robot, start_euler)
            jumped = max_speed > JUMP_FACTOR * DESCENT_SPEED
            jumps += jumped
            print(f"cycle {cycle:2d}: descent max {max_speed * 1000:5.1f} mm/s"
                  f"{'  <-- JUMP' if jumped else ''}, move_linear back {DROP / duration * 1000:4.1f} mm/s")
    finally:
        shut_down(robot, start_euler)
    print(f"\n{jumps} jumps in {args.cycles} cycles (commanded {DESCENT_SPEED * 1000:.1f} mm/s)")


if __name__ == "__main__":
    main()
