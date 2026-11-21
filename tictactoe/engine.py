"""Move selection: exact negamax over the full game tree, with optional deliberate mistakes.

Scores are from the point of view of the player to move: a win scores 10 - plies, a loss -(10 - plies),
a draw 0, where plies is the number of marks on the board when the game ends. Counting marks on the board
(instead of moves from the search root) keeps the score a function of the position alone, so it can be
cached, and still makes the engine win as fast and lose as slowly as possible.
"""

import random
from functools import lru_cache

from .board import Board, Cell, legal_moves, other, play, winner

# probability of playing a random legal move instead of an optimal one
DIFFICULTIES = {"perfect": 0.0, "medium": 0.3, "easy": 0.7}


@lru_cache(maxsize=None)  # fewer than 5478 reachable positions x 2 players
def negamax(board: Board, player: Cell) -> int:
    """Value of `board` for `player`, who is to move, under perfect play from both sides."""
    w = winner(board)
    plies = 9 - board.count(Cell.EMPTY)
    if w is not None:
        return 10 - plies if w is player else -(10 - plies)
    moves = legal_moves(board)
    if not moves:
        return 0
    opponent = other(player)
    return max(-negamax(play(board, i, player), opponent) for i in moves)


def scored_moves(board: Board, player: Cell) -> dict[int, int]:
    """Value of each legal move for `player`, from `player`'s point of view."""
    opponent = other(player)
    return {i: -negamax(play(board, i, player), opponent) for i in legal_moves(board)}


def _epsilon(difficulty: str | float) -> float:
    if isinstance(difficulty, str):
        try:
            return DIFFICULTIES[difficulty]
        except KeyError:
            raise ValueError(f"unknown difficulty {difficulty!r}, expected one of {list(DIFFICULTIES)} "
                             "or a probability 0-1") from None
    eps = float(difficulty)
    if not 0.0 <= eps <= 1.0:
        raise ValueError(f"difficulty must be between 0 and 1, got {eps}")
    return eps


def best_move(board: Board, player: Cell, difficulty: str | float = "perfect",
              rng: random.Random | None = None) -> int:
    """Cell index (0-8) for `player` to play.

    `difficulty` is 'perfect', 'medium', 'easy', or the probability (0-1) of playing a random legal move
    instead of an optimal one. Among equally good optimal moves one is chosen at random, so games vary.
    Pass a seeded `rng` for reproducible choices. Raises ValueError if the game is already over.
    """
    eps = _epsilon(difficulty)
    rng = rng or random.Random()
    scores = scored_moves(board, player)
    if not scores:
        raise ValueError("game is over, no legal moves")
    if eps > 0 and rng.random() < eps:
        return rng.choice(sorted(scores))
    top = max(scores.values())
    return rng.choice(sorted(i for i, s in scores.items() if s == top))
