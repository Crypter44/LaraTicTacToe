"""Reconcile what vision sees with the game state the robot knows.

The robot knows the board exactly up to the human's last move: its own marks it drew itself, the human's
earlier marks were already accepted. A new capture should therefore differ from the known board by exactly
one new human mark, or by nothing if the human hasn't moved yet. Everything else is a vision error or the
human doing something odd (two marks, wrong symbol, wiping a mark), which this module tells apart.

Robot marks are trusted from the known board: if vision misreads one of them as empty, that is only noted
in `Observation.detail`. A confidently seen human symbol on a robot cell is INVALID though, since it means
someone drew over it (or the camera is badly misaligned).

`fuse` turns several captures into one board with per-cell confidences (vote share), so the
classifier's per-frame output can be passed straight to `validate`.
"""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from .board import Board, Cell, other

NO_CHANGE = "no_change"    # human hasn't moved: wait and capture again
HUMAN_MOVE = "human_move"  # exactly one new human mark at `move`: accept it
UNCERTAIN = "uncertain"    # a relevant cell is below min_conf: capture again
INVALID = "invalid"        # the board can't follow from the known one: retry, then ask the operator

MIN_CONF = 0.6


@dataclass(frozen=True)
class Observation:
    kind: str
    move: int | None = None
    detail: str = ""


def validate(known: Board, perceived: Sequence[Cell], confidence: Sequence[float] | None = None,
             human: Cell = Cell.O, min_conf: float = MIN_CONF) -> Observation:
    """Compare a perceived board (9 cells, optionally with confidences 0-1) with the known board.

    Confidently wrong cells make the result INVALID, otherwise any cell that differs from the known board
    or would be a new mark but is below `min_conf` makes it UNCERTAIN. Only then are new human marks
    counted: none is NO_CHANGE, one is HUMAN_MOVE, more is INVALID.
    """
    perceived = [Cell(c) for c in perceived]
    if len(known) != 9 or len(perceived) != 9:
        raise ValueError(f"boards must have 9 cells, got {len(known)} known and {len(perceived)} perceived")
    if confidence is None:
        confidence = [1.0] * 9
    elif len(confidence) != 9:
        raise ValueError(f"expected 9 confidences, got {len(confidence)}")
    robot = other(human)

    invalid, uncertain, notes, new_marks = [], [], [], []
    for i, (was, seen, conf) in enumerate(zip(known, perceived, confidence)):
        sure = conf >= min_conf
        if was is robot:
            if seen is human and sure:
                invalid.append(f"cell {i}: robot's {robot.value} seen as {human.value}")
            elif seen is not robot:
                notes.append(f"cell {i}: robot's {robot.value} seen as {seen.value!r} ({conf:.2f}), ignored")
        elif was is human:
            if seen is not human:
                msg = f"cell {i}: human's {human.value} seen as {seen.value!r} ({conf:.2f})"
                (invalid if sure else uncertain).append(msg)
        elif not sure:  # was empty: even a faint "empty" might hide a new mark
            uncertain.append(f"cell {i}: {seen.value!r} at confidence {conf:.2f}")
        elif seen is robot:
            invalid.append(f"cell {i}: new {robot.value}, but the human plays {human.value}")
        elif seen is human:
            new_marks.append(i)

    if invalid:
        return Observation(INVALID, detail="; ".join(invalid + uncertain + notes))
    if uncertain:
        return Observation(UNCERTAIN, detail="; ".join(uncertain + notes))
    if len(new_marks) > 1:
        return Observation(INVALID, detail="; ".join([f"{len(new_marks)} new marks at {new_marks}"] + notes))
    if new_marks:
        return Observation(HUMAN_MOVE, move=new_marks[0], detail="; ".join(notes))
    return Observation(NO_CHANGE, detail="; ".join(notes))


_TIE_ORDER = (Cell.EMPTY, Cell.X, Cell.O)  # on a tied vote prefer EMPTY; its low share flags it anyway


def fuse(readings: Sequence[Sequence[Cell]]) -> tuple[Board, tuple[float, ...]]:
    """Per-cell majority vote over several captures. Returns (board, confidence = winning vote share)."""
    if not readings:
        raise ValueError("need at least one reading")
    if any(len(r) != 9 for r in readings):
        raise ValueError("every reading must have 9 cells")
    board, confidence = [], []
    for i in range(9):
        votes = Counter(Cell(r[i]) for r in readings)
        cell = max(_TIE_ORDER, key=lambda c: (votes[c], -_TIE_ORDER.index(c)))
        board.append(cell)
        confidence.append(votes[cell] / len(readings))
    return tuple(board), tuple(confidence)
