"""Find the board height under the pen: lower it slowly until the joint torques show contact.

The LARA has no force sensor (get_tcp_force is always 0), so contact is detected from one joint torque
(SIGNAL_JOINT): when the board carries part of the arm's weight, that torque moves away from its value in
the air. Rules learned on the real arm, see tests/probe_test.py and tests/servo_cycle_test.py:
  - Joint friction makes the torque wobble ±2-3 Nm while moving, so the threshold is 6 Nm (~10 N at the pen).
  - The arm keeps moving ~1 s after stop_movelinear_online, so descend at 0.5 mm/s (~0.4 mm overshoot).
  - Once the servo interface jumped to an old setpoint after being switched back on. That only happened after
    a stop while pressing the board, so every probe ends with an online move back into the air before the
    servo interface is switched off, and starts with a "hold" target at the current position.
"""

import statistics
import time

PROBE_SPEED = 0.0005       # m/s downwards
LIFT_SPEED = 0.002         # m/s requested for lifting off the board (the robot was seen doing only ~0.5)
ACCELERATION = 0.05        # m/s²
MAX_TRAVEL = 0.015         # m, a probe gives up if there is no board this far below its start
SAFE_LIFT = 0.002          # m above the contact where the probe ends

AT_TARGET = 0.0002         # m, closer than this counts as arrived
SPEED_MARGIN = 0.001       # m the arm may be ahead of the commanded descent before the watchdog stops it
STALL_DISTANCE = 0.00005   # m the arm must rise within STALL_TIME while lifting, otherwise it counts as stuck
STALL_TIME = 1.0           # s

# Torque of which joint is watched (0-based index). It must turn smoothly during the descent, otherwise its
# friction sticks and slips and the torque saw-tooths by ±5 Nm. With the pen at z ≈ 38 cm, joint 2 (shoulder)
# turns only 0.009°/mm and saw-tooths, joint 3 (elbow) turns 0.125°/mm. Lever for a vertical force at the pen
# there: joint 2 0.56 m, joint 3 0.42 m, so 6 Nm on joint 3 ≈ 14 N. (At z ≈ 8 cm the shoulder did the work.)
SIGNAL_JOINT = 2
# After the arm starts moving, the torque drifts until the joint friction has turned to the new direction:
# ~1 s with the board at z ≈ 8 cm, over 3 s at z ≈ 38 cm. So wait until it stops drifting, not a fixed time.
MIN_SETTLE_TIME = 1.0      # s, never take the baseline earlier
MAX_SETTLE_TIME = 6.0      # s, give up if the torque still drifts after this
SLOPE_WINDOW = 1.0         # s over which the drift is measured
SETTLED_SLOPE = 1.5        # Nm/s, less drift than this counts as settled (the start ramp was 4-5 Nm/s)
BASELINE_TIME = 1.5        # s of descent in the air used as the no-contact reference
AVERAGE_SAMPLES = 10       # loop samples (~0.1 s) averaged to smooth the noise
# Nm away from the baseline that counts as contact. Joint 3 at z ≈ 38 cm stayed within ~1.5 Nm in the air
# and rises ~2.5-3 Nm/mm on contact, so 3.5 Nm (~8 N at the pen) leaves a factor 2 margin. (Joint 2 at
# z ≈ 8 cm needed 6 Nm because it wobbled ±2-3 Nm while moving.)
THRESHOLD = 3.5


class SafetyError(RuntimeError):
    """The arm did something it was not told to do, or the board is not where it should be."""


class Prober:
    def __init__(self, robot, threshold: float = THRESHOLD, joint: int = SIGNAL_JOINT):
        """`robot` is a connected neurapy Robot in automatic mode with the servo interface switched off.
        `joint` is the 0-based index of the joint whose torque signals contact."""
        self.robot = robot
        self.threshold = threshold
        self.joint = joint
        self.log = []  # rows (t, z, torque, deviation, phase, *all 6 torques) of the last descent

    def probe(self, start: list[float]) -> float:
        """Probe straight down from `start` ([x, y, z, qw, qx, qy, qz]), where the pen must already be,
        in the air. Returns the contact z. Ends SAFE_LIFT above the contact with the servo interface off."""
        self._activate_servo()
        try:
            contact_z = self._descend_until_contact(start)
            self._lift_online(with_z(start, contact_z + SAFE_LIFT))
        finally:
            self.robot.stop_movelinear_online()
            self.robot.deactivate_servo_interface()
        return contact_z

    def _activate_servo(self) -> None:
        """Switch on online motion, then send the current position as target so the online motion starts
        from where the arm really is. Both times check that the arm stays still."""
        before = self._pose()
        self.robot.activate_servo_interface("position")
        self._expect_still(before[2], "after switching on the servo interface")
        send_target(self.robot, before, PROBE_SPEED)
        self._expect_still(before[2], "after the hold target")

    def _descend_until_contact(self, start: list[float]) -> float:
        """Three phases: 'settling' until the torque stops drifting, 'baseline' to learn its value in the air,
        'watching' until it moves more than the threshold away from that value."""
        target_z = start[2] - MAX_TRAVEL
        send_target(self.robot, with_z(start, target_z), PROBE_SPEED)
        samples, baseline = [], []  # samples: (t, torque) of the whole descent
        phase, baseline_start, baseline_mean = "settling", None, None
        self.log = []
        start_time = time.perf_counter()

        while (t := time.perf_counter() - start_time) < MAX_TRAVEL / PROBE_SPEED + 3.0:
            z = self._pose()[2]
            depth = start[2] - z
            if depth > PROBE_SPEED * t + SPEED_MARGIN:
                raise SafetyError(f"arm is {depth * 1000:.1f} mm down after {t:.2f} s, faster than commanded")
            if t > 2 * MIN_SETTLE_TIME and depth < AT_TARGET:
                raise SafetyError("arm does not move: the descent target was ignored")

            torques = self.robot.get_current_joint_torques()
            torque = torques[self.joint]
            samples.append((t, torque))
            deviation = 0.0
            if phase == "settling" and t >= MIN_SETTLE_TIME and abs(torque_slope(samples)) < SETTLED_SLOPE:
                phase, baseline_start = "baseline", t
            elif phase == "settling" and t > MAX_SETTLE_TIME:
                raise SafetyError(f"joint {self.joint + 1} torque still drifts {torque_slope(samples):.1f} Nm/s "
                                  f"after {t:.0f} s")
            elif phase == "baseline":
                baseline.append(torque)
                if t >= baseline_start + BASELINE_TIME:
                    phase, baseline_mean = "watching", statistics.mean(baseline)
            elif phase == "watching":
                recent = [s[1] for s in samples[-AVERAGE_SAMPLES:]]
                deviation = abs(statistics.mean(recent) - baseline_mean)
            self.log.append((t, z, torque, deviation, phase, *torques))

            if deviation > self.threshold:
                self.robot.stop_movelinear_online()
                wait_until_still(self.robot)
                return z
            if z <= target_z + AT_TARGET:
                break
        raise SafetyError(f"no board within {MAX_TRAVEL * 1000:.0f} mm below the start")

    def _lift_online(self, target: list[float]) -> None:
        """Move up to `target` with the servo interface still on, so its last setpoint is in the air."""
        send_target(self.robot, target, LIFT_SPEED)
        low_z = progress_z = self._pose()[2]
        progress_time = time.perf_counter()
        while abs((z := self._pose()[2]) - target[2]) > AT_TARGET:
            if z < low_z - SPEED_MARGIN:
                raise SafetyError("arm moves down while it should lift")
            if z > progress_z + STALL_DISTANCE:
                progress_z, progress_time = z, time.perf_counter()
            elif time.perf_counter() - progress_time > STALL_TIME:
                raise SafetyError("arm stopped lifting off the board")
            time.sleep(0.02)
        wait_until_still(self.robot)  # a new target is ignored while this motion is still finishing

    def _expect_still(self, z: float, when: str) -> None:
        time.sleep(0.3)
        if abs(self._pose()[2] - z) > AT_TARGET:
            raise SafetyError(f"arm moved by itself {when}")

    def _pose(self) -> list[float]:
        return self.robot.get_tcp_pose_quaternion()


def send_target(robot, pose: list[float], speed: float) -> None:
    """Start a straight online move to `pose`. Returns immediately. A new target sent while the arm
    still moves is ignored, so stop or wait until it is still first."""
    velocity = [speed] * 3 + [0.1] * 3  # translation m/s, rotation rad/s (orientation stays the same)
    acceleration = [ACCELERATION] * 3 + [0.1] * 3
    code = robot.movelinear_online(pose, velocity, acceleration)
    if code is not None and code >= 3:  # NEURA's examples treat codes below 3 as warnings, 3+ as errors
        raise RuntimeError(f"movelinear_online refused the target, error code {code}")


def torque_slope(samples: list[tuple[float, float]]) -> float:
    """Drift in Nm/s over the last SLOPE_WINDOW: mean of its second half minus mean of its first half."""
    now = samples[-1][0]
    window = [s for s in samples if s[0] >= now - SLOPE_WINDOW]
    middle = now - SLOPE_WINDOW / 2
    first = [torque for t, torque in window if t < middle]
    second = [torque for t, torque in window if t >= middle]
    if not first or not second:
        return float("inf")  # not enough data yet, never counts as settled
    return (statistics.mean(second) - statistics.mean(first)) / (SLOPE_WINDOW / 2)


def with_z(pose: list[float], z: float) -> list[float]:
    return [pose[0], pose[1], z, *pose[3:]]


def wait_until_still(robot, timeout: float = 2.0) -> float:
    """Wait until z changes less than 0.02 mm within 0.1 s. Returns that z."""
    start_time = time.perf_counter()
    z = robot.get_tcp_pose_quaternion()[2]
    while True:
        time.sleep(0.1)
        new_z = robot.get_tcp_pose_quaternion()[2]
        if abs(new_z - z) < 0.00002:
            return new_z
        if time.perf_counter() - start_time > timeout:
            raise SafetyError("arm did not come to rest")
        z = new_z
