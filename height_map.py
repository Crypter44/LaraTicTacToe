"""Board heights measured on a regular grid along the board's edges, with bilinear interpolation in between.

    heights = HeightMap.load("board_heights.json")
    z = heights.z_at(x, y)       # probed board height at any point (x, y) of the robot base frame (m)

The grid lies in board coordinates (u, v): offsets from the board centre along its edges. The board may be
turned against the robot's x/y axes by `rotation_deg`, e.g. 45° when it looks like a diamond from the robot.
"""

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class HeightMap:
    us: list[float]            # grid positions along the board's first edge, offsets from the centre, ascending (m)
    vs: list[float]            # grid positions along the board's second edge, ascending
    z: list[list[float]]       # z[row][col] is the height at (us[col], vs[row])
    center_pose: list[float]   # pose [x, y, z, roll, pitch, yaw] above the board centre used for calibration
    rotation_deg: float = 0.0  # board edges turned this much against the robot base x/y axes

    def z_at(self, x: float, y: float) -> float:
        """Height at (x, y) in the robot base frame. Outside the grid the edge values are continued."""
        u, v = self.to_board(x, y)
        col, fu = _bracket(self.us, u)
        row, fv = _bracket(self.vs, v)
        z00, z01 = self.z[row][col], self.z[row][col + 1]
        z10, z11 = self.z[row + 1][col], self.z[row + 1][col + 1]
        return (z00 * (1 - fu) + z01 * fu) * (1 - fv) + (z10 * (1 - fu) + z11 * fu) * fv

    def to_board(self, x: float, y: float) -> tuple[float, float]:
        """Robot base (x, y) -> board (u, v)."""
        dx, dy = x - self.center_pose[0], y - self.center_pose[1]
        c, s = math.cos(math.radians(self.rotation_deg)), math.sin(math.radians(self.rotation_deg))
        return dx * c + dy * s, -dx * s + dy * c

    def to_base(self, u: float, v: float) -> tuple[float, float]:
        """Board (u, v) -> robot base (x, y)."""
        return board_to_base(self.center_pose, self.rotation_deg, u, v)

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls, path: Path) -> "HeightMap":
        return cls(**json.loads(Path(path).read_text()))


def board_to_base(center_pose: list[float], rotation_deg: float, u: float, v: float) -> tuple[float, float]:
    """Board offsets (u, v) from the centre -> robot base (x, y)."""
    c, s = math.cos(math.radians(rotation_deg)), math.sin(math.radians(rotation_deg))
    return center_pose[0] + u * c - v * s, center_pose[1] + u * s + v * c


def _bracket(values: list[float], v: float) -> tuple[int, float]:
    """Index i of the grid cell [values[i], values[i + 1]] containing v, and v's fraction across it (0-1)."""
    i = 0
    while i < len(values) - 2 and v > values[i + 1]:
        i += 1
    fraction = (v - values[i]) / (values[i + 1] - values[i])
    return i, min(1.0, max(0.0, fraction))
