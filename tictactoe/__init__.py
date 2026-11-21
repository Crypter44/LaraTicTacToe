"""Tic-tac-toe brain for the LARA 5: rules, move selection, and checking vision against the known game.

Pure Python, no hardware. See board.py for the cell numbering (index 0-8 = drawer cell 1-9).

Intended use by the game state machine (not implemented here):

    known = EMPTY_BOARD
    HOME -> CAPTURE (N frames from the home pose, classified per cell)
         -> board, conf = fuse(frames)
         -> obs = validate(known, board, conf, human=HUMAN)
              NO_CHANGE / UNCERTAIN -> CAPTURE again
              INVALID               -> retry a few times, then ask the operator
              HUMAN_MOVE            -> known = play(known, obs.move, HUMAN)
         -> if status(known) != ONGOING: game over (optionally strike through winning_line(known))
         -> idx = best_move(known, ROBOT, difficulty)
         -> drawer.draw(ROBOT.value.lower(), to_cell(idx)); known = play(known, idx, ROBOT)
         -> if status(known) != ONGOING: game over
         -> HOME

If the robot starts, skip straight to best_move on the empty board.
"""

from .board import (
    DRAW, EMPTY_BOARD, LINES, O_WINS, ONGOING, X_WINS, Board, Cell, from_cell, from_string, is_full,
    legal_moves, other, play, render, status, to_cell, to_string, whose_turn, winner, winning_line,
)
from .engine import DIFFICULTIES, best_move, negamax, scored_moves
from .validate import HUMAN_MOVE, INVALID, MIN_CONF, NO_CHANGE, UNCERTAIN, Observation, fuse, validate

__all__ = [
    "DRAW", "EMPTY_BOARD", "LINES", "O_WINS", "ONGOING", "X_WINS", "Board", "Cell", "from_cell", "from_string",
    "is_full", "legal_moves", "other", "play", "render", "status", "to_cell", "to_string", "whose_turn",
    "winner", "winning_line",
    "DIFFICULTIES", "best_move", "negamax", "scored_moves",
    "HUMAN_MOVE", "INVALID", "MIN_CONF", "NO_CHANGE", "UNCERTAIN", "Observation", "fuse", "validate",
]
