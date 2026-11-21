"""Tic-tac-toe board representation and rules.

A board is an immutable tuple of 9 `Cell`s. Index = row * 3 + col, row 0 is the top row as seen by the
camera from the home pose, col 0 the left column:

     0 | 1 | 2
     3 | 4 | 5
     6 | 7 | 8

board_drawer.py and main.py use the same numbering, so an index can be passed straight to the drawer.
The drawer puts row 0 at +v on the board; the camera image has to be oriented the same way, or vision's
output must be remapped.
"""

from enum import Enum


class Cell(str, Enum):
    EMPTY = " "
    X = "X"
    O = "O"  # noqa: E741

    def __str__(self) -> str:
        return self.value


Board = tuple[Cell, ...]

EMPTY_BOARD: Board = (Cell.EMPTY,) * 9

LINES: tuple[tuple[int, int, int], ...] = (
    (0, 1, 2), (3, 4, 5), (6, 7, 8),  # rows
    (0, 3, 6), (1, 4, 7), (2, 5, 8),  # columns
    (0, 4, 8), (2, 4, 6),             # diagonals
)

ONGOING, X_WINS, O_WINS, DRAW = "ongoing", "x_wins", "o_wins", "draw"


def other(player: Cell) -> Cell:
    if player is Cell.X:
        return Cell.O
    if player is Cell.O:
        return Cell.X
    raise ValueError(f"not a player: {player!r}")


def winning_line(board: Board) -> tuple[int, int, int] | None:
    """The first completed line, e.g. to strike it through. None if nobody has won."""
    for line in LINES:
        a, b, c = (board[i] for i in line)
        if a is not Cell.EMPTY and a is b is c:
            return line
    return None


def winner(board: Board) -> Cell | None:
    line = winning_line(board)
    return board[line[0]] if line else None


def is_full(board: Board) -> bool:
    return Cell.EMPTY not in board


def legal_moves(board: Board) -> list[int]:
    """Empty cells, or none once the game is over."""
    if winner(board) is not None:
        return []
    return [i for i, cell in enumerate(board) if cell is Cell.EMPTY]


def play(board: Board, idx: int, player: Cell) -> Board:
    """The board after `player` marks cell `idx`. Raises ValueError if the cell is taken or out of range."""
    if player not in (Cell.X, Cell.O):
        raise ValueError(f"not a player: {player!r}")
    if not 0 <= idx < 9:
        raise ValueError(f"cell index out of range: {idx}")
    if board[idx] is not Cell.EMPTY:
        raise ValueError(f"cell {idx} is already taken by {board[idx].value}")
    return board[:idx] + (player,) + board[idx + 1:]


def whose_turn(board: Board, first: Cell = Cell.X) -> Cell:
    """The player to move, given who started. Raises ValueError if the mark counts can't come from a game."""
    own, opp = board.count(first), board.count(other(first))
    if own == opp:
        return first
    if own == opp + 1:
        return other(first)
    raise ValueError(f"impossible mark counts: {first.value}={own}, {other(first).value}={opp}")


def status(board: Board) -> str:
    """'ongoing', 'x_wins', 'o_wins' or 'draw'."""
    w = winner(board)
    if w is Cell.X:
        return X_WINS
    if w is Cell.O:
        return O_WINS
    return DRAW if is_full(board) else ONGOING


_CHARS = {"X": Cell.X, "x": Cell.X, "O": Cell.O, "o": Cell.O, ".": Cell.EMPTY, " ": Cell.EMPTY, "-": Cell.EMPTY}


def from_string(text: str) -> Board:
    """'X.O......' -> board. '.', '-' and ' ' are empty; '|', '/' and newlines are ignored."""
    chars = [ch for ch in text if ch not in "|/\n"]
    if len(chars) != 9:
        raise ValueError(f"expected 9 cells, got {len(chars)}: {text!r}")
    try:
        return tuple(_CHARS[ch] for ch in chars)
    except KeyError as e:
        raise ValueError(f"unknown cell character {e.args[0]!r} in {text!r}") from None


def to_string(board: Board) -> str:
    """Board -> 'X.O......' (round-trips with from_string)."""
    return "".join("." if cell is Cell.EMPTY else cell.value for cell in board)


def render(board: Board) -> str:
    """Three-line picture for the console."""
    rows = [" | ".join(cell.value for cell in board[r * 3:r * 3 + 3]) for r in range(3)]
    return "\n---------\n".join(f" {row} " for row in rows)
