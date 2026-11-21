import random
import unittest

from tictactoe import (
    EMPTY_BOARD, ONGOING, O_WINS, X_WINS, Cell, best_move, from_string, legal_moves, other, play, scored_moves,
    status,
)


def top_moves(board, player):
    scores = scored_moves(board, player)
    best = max(scores.values())
    return [i for i, s in scores.items() if s == best]


class EngineTest(unittest.TestCase):
    def test_takes_immediate_win(self):
        board = from_string("XX.|O.O|...")  # X to move; O also threatens 4
        for seed in range(20):
            self.assertEqual(best_move(board, Cell.X, rng=random.Random(seed)), 2)

    def test_blocks_immediate_loss(self):
        board = from_string("XX.|.O.|...")  # O to move, must block 2
        for seed in range(20):
            self.assertEqual(best_move(board, Cell.O, rng=random.Random(seed)), 2)

    def test_prefers_faster_win(self):
        board = from_string("XX.|O.O|...")
        scores = scored_moves(board, Cell.X)
        self.assertGreater(scores[4], 0)  # 4 also wins by force, just later
        self.assertGreater(scores[2], scores[4])

    def test_never_loses(self):
        """Engine (any of its optimal choices) against every possible opponent move sequence."""
        def explore(board, to_move, engine):
            result = status(board)
            if result != ONGOING:
                self.assertNotEqual(result, O_WINS if engine is Cell.X else X_WINS, board)
                return
            moves = top_moves(board, engine) if to_move is engine else legal_moves(board)
            for i in moves:
                explore(play(board, i, to_move), other(to_move), engine)

        for engine in (Cell.X, Cell.O):
            with self.subTest(engine=engine):
                explore(EMPTY_BOARD, Cell.X, engine)

    def test_perfect_vs_perfect_is_draw(self):
        self.assertEqual(max(scored_moves(EMPTY_BOARD, Cell.X).values()), 0)
        for seed in range(20):
            rng = random.Random(seed)
            board, player = EMPTY_BOARD, Cell.X
            while status(board) == ONGOING:
                board = play(board, best_move(board, player, rng=rng), player)
                player = other(player)
            self.assertEqual(status(board), "draw")

    def test_perfect_varies_between_equal_moves(self):
        moves = {best_move(EMPTY_BOARD, Cell.X, rng=random.Random(seed)) for seed in range(50)}
        self.assertGreater(len(moves), 1)
        self.assertTrue(moves <= set(top_moves(EMPTY_BOARD, Cell.X)))

    def test_seeded_easy_is_reproducible(self):
        board = from_string("XX.|O.O|...")
        for difficulty in ("easy", "medium", 0.5):
            a = [best_move(board, Cell.X, difficulty, random.Random(seed)) for seed in range(30)]
            b = [best_move(board, Cell.X, difficulty, random.Random(seed)) for seed in range(30)]
            self.assertEqual(a, b)

    def test_easy_makes_mistakes(self):
        board = from_string("XX.|O.O|...")
        moves = [best_move(board, Cell.X, "easy", random.Random(seed)) for seed in range(100)]
        self.assertTrue(any(m != 2 for m in moves))
        self.assertTrue(all(m in legal_moves(board) for m in moves))
        always_random = [best_move(board, Cell.X, 1.0, random.Random(seed)) for seed in range(100)]
        self.assertGreater(len(set(always_random)), 2)

    def test_rejects_bad_difficulty(self):
        for difficulty in ("hard", -0.1, 1.5):
            with self.assertRaises(ValueError):
                best_move(EMPTY_BOARD, Cell.X, difficulty)

    def test_raises_on_finished_board(self):
        for text in ("XXX|OO.|...", "XOX|XOO|OXX"):
            with self.assertRaises(ValueError):
                best_move(from_string(text), Cell.O)


if __name__ == "__main__":
    unittest.main()
