"""Draws X and O into the cells of a tic-tac-toe board with the NEURA LARA 5.

Cells are numbered like this:      1 | 2 | 3
                                   4 | 5 | 6
                                   7 | 8 | 9

Everything comes from the board calibration (calibrate_board.py -> board_heights.json): the board centre,
how far the board is turned against the robot's axes, and the board height at every point. Drawings are
planned in board coordinates (u, v), offsets from the centre along the board edges, and converted to robot
coordinates only when moving. The pen keeps the orientation it had during calibration.
"""

import itertools
import math

from height_map import HeightMap

CELL_SIZE = 0.08       # m between the centres of two neighbouring cells
SYMBOL_SIZE = 0.04     # m, width of an X and diameter of an O
LIFT = 0.04            # m the pen rises between strokes
# Issue #2: the arm was unsteady for the first ~2 cm of every stroke once strokes were sent as one blended
# move through waypoints every 2 cm; single-target moves (and teach mode) never showed it. Along a straight
# line the board height deviates only ~0.2 mm from a straight line between its ends, so straight lines go as
# one move again. Both options below stay switchable for tests/stroke_test.py.
SEGMENT_LENGTH = 0.0   # m, split strokes into waypoints this far apart to follow the height map; 0 = off
LEAD_IN = 0.0          # m run-up in the air before each stroke, the pen touches down while moving; 0 = off
LEAD_IN_HEIGHT = 0.003 # m above the board at the start of the run-up
# m above the probed height while drawing. The probe stops ~1 mm after the pen first touches, so the probed
# height lies ~1 mm inside the board; +0.5 mm leaves a light press.
DRAW_OFFSET = 0.0005

SPEED = 0.02           # m/s
ACCELERATION = 0.1     # m/s²
BLEND_RADIUS = 0.0005  # m, lets the pen round the corners between points instead of stopping at each

Point = tuple[float, float]  # board coordinates (u, v) in m
Stroke = list[Point]         # points drawn in one go, without lifting the pen


class BoardDrawer:
    def __init__(self, robot, heights: HeightMap, offset: float = DRAW_OFFSET, lead_in: float = LEAD_IN,
                 segment_length: float = SEGMENT_LENGTH):
        """`robot` is a connected neurapy Robot in automatic mode, `heights` the board calibration,
        `offset` the pen height above the probed board height while drawing, `lead_in` the run-up length,
        `segment_length` the waypoint spacing along strokes (0 = only the stroke's own points)."""
        self.robot = robot
        self.heights = heights
        self.offset = offset
        self.lead_in = lead_in
        self.segment_length = segment_length
        self.orientation = heights.center_pose[3:]

    def draw(self, symbol: str, cell: int) -> None:
        """Draw 'x' or 'o' into a cell (1-9). Starts and ends with the pen parked above the board centre."""
        cu, cv = self._cell_center(cell)
        self.park()
        if symbol == "x":
            for stroke in self._x_strokes(cu, cv):
                self.draw_stroke(stroke)
        else:
            self.draw_circle(cu, cv)
        self.park()

    def draw_grid(self) -> None:
        """Draw the two lines along each board edge that separate the cells."""
        self.park()
        for stroke in self._grid_strokes():
            self.draw_stroke(stroke)
        self.park()

    def park(self) -> None:
        """Hover above the board centre."""
        # TODO make the robot move to a safe pose above the board centre, instead of just hovering above it
        # Especially, the robot should be in a position that the camera can see the board, so that the camera can be used to check the result of the drawing.
        self._move_linear([self._pose_at(0.0, 0.0, lift=LIFT)])

    @staticmethod
    def _cell_center(cell: int) -> Point:
        row, col = divmod(cell - 1, 3)
        return (col - 1) * CELL_SIZE, -(row - 1) * CELL_SIZE  # row 0 is the top row, which lies at +v

    @staticmethod
    def _grid_strokes() -> list[Stroke]:
        edge = 1.5 * CELL_SIZE   # from the centre to the outer edge of the board
        line = 0.5 * CELL_SIZE   # from the centre to a grid line
        return [
            [(-line, -edge), (-line, edge)],
            [(line, -edge), (line, edge)],
            [(-edge, -line), (edge, -line)],
            [(-edge, line), (edge, line)],
        ]

    @staticmethod
    def _x_strokes(cu: float, cv: float) -> list[Stroke]:
        h = SYMBOL_SIZE / 2
        return [
            [(cu - h, cv - h), (cu + h, cv + h)],
            [(cu - h, cv + h), (cu + h, cv - h)],
        ]

    def draw_circle(self, cu: float, cv: float) -> None:
        """Draw a circle around (cu, cv) as two half circles with move_circular, which takes an arc's start,
        middle and end point. A polygon sent as one blended move made the pen unsteady at the start (issue #2)."""
        r = SYMBOL_SIZE / 2
        right, top, left, bottom = [(cu + r * math.cos(a), cv + r * math.sin(a)) for a in
                                    (0, math.pi / 2, math.pi, 3 * math.pi / 2)]
        self._move_linear([self._pose_at(*right, lift=LIFT)])
        self._move_linear([self._pose_at(*right)])
        self._move_circular([self._pose_at(*right), self._pose_at(*top), self._pose_at(*left)])
        self._move_circular([self._pose_at(*left), self._pose_at(*bottom), self._pose_at(*right)])
        self._move_linear([self._pose_at(*right, lift=LIFT)])

    def draw_stroke(self, stroke: Stroke) -> None:
        """Hover above the run-up start, lower the pen to just above the board, run up and draw through all
        points in one smooth motion, lift the pen."""
        points = _subdivide(stroke, self.segment_length)
        if self.lead_in > 0:
            start, height, path = self._run_up_start(points), LEAD_IN_HEIGHT, points
        else:  # old behaviour: lower straight onto the first point, then draw from there
            start, height, path = points[0], 0.0, points[1:]
        self._move_linear([self._pose_at(*start, lift=LIFT)])
        self._move_linear([self._pose_at(*start, lift=height)])
        self._move_linear([self._pose_at(*point) for point in path])
        self._move_linear([self._pose_at(*points[-1], lift=LIFT)])

    def _run_up_start(self, points: Stroke) -> Point:
        """Point `lead_in` before the stroke, continuing its first direction backwards."""
        (u0, v0), (u1, v1) = points[0], points[1]
        length = math.hypot(u1 - u0, v1 - v0)
        return u0 - (u1 - u0) / length * self.lead_in, v0 - (v1 - v0) / length * self.lead_in

    def _pose_at(self, u: float, v: float, lift: float = 0.0) -> list[float]:
        """Robot pose at board point (u, v): measured board height + offset + `lift`."""
        x, y = self.heights.to_base(u, v)
        return [x, y, self.heights.z_at(x, y) + self.offset + lift, *self.orientation]

    def _move_linear(self, poses: list[list[float]]) -> None:
        """Straight lines through all poses. Several poses are blended into one smooth path."""
        if len(poses) == 1:
            self.robot.move_linear(target_pose=poses, speed=SPEED, acceleration=ACCELERATION,
                                   enable_safety=True)
        else:
            self.robot.move_linear(target_pose=poses, speed=SPEED, acceleration=ACCELERATION,
                                   enable_safety=True, blending=True, blending_mode=2,
                                   blend_radius=BLEND_RADIUS)

    def _move_circular(self, poses: list[list[float]]) -> None:
        """Arc through three poses: start (the current pose), a point on the arc, end."""
        self.robot.move_circular(target_pose=poses, speed=SPEED, acceleration=ACCELERATION, enable_safety=True)


def _subdivide(stroke: Stroke, max_length: float) -> Stroke:
    """Insert points so no piece of the stroke is longer than `max_length` (0 = leave the stroke as it is)."""
    if max_length <= 0:
        return list(stroke)
    points = [stroke[0]]
    for (u0, v0), (u1, v1) in itertools.pairwise(stroke):
        pieces = max(1, math.ceil(math.hypot(u1 - u0, v1 - v0) / max_length))
        points += [(u0 + (u1 - u0) * i / pieces, v0 + (v1 - v0) * i / pieces) for i in range(1, pieces + 1)]
    return points
