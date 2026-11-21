import unittest

from tictactoe import (
    DRAW, EMPTY_BOARD, LINES, O_WINS, ONGOING, X_WINS, Cell, from_cell, from_string, is_full, legal_moves,
    other, play, status, to_cell, to_string, whose_turn, winner, winning_line,
)


class BoardTest(unittest.TestCase):
    def test_all_lines_win(self):
        self.assertEqual(len(LINES), 8)
        for player in (Cell.X, Cell.O):
            for line in LINES:
                board = tuple(player if i in line else Cell.EMPTY for i in range(9))
                self.assertEqual(winner(board), player)
                self.assertEqual(winning_line(board), line)
                self.assertEqual(status(board), X_WINS if player is Cell.X else O_WINS)
                self.assertEqual(legal_moves(board), [])

    def test_no_winner(self):
        for text in (".........", "XO.......", "XOX.O.O.X"):
            board = from_string(text)
            self.assertIsNone(winner(board))
            self.assertIsNone(winning_line(board))
            self.assertEqual(status(board), ONGOING)

    def test_draw(self):
        board = from_string("XOX|XOO|OXX")
        self.assertTrue(is_full(board))
        self.assertIsNone(winner(board))
        self.assertEqual(status(board), DRAW)
        self.assertEqual(legal_moves(board), [])

    def test_win_on_full_board_is_not_draw(self):
        board = from_string("XOX|OXO|OXX")
        self.assertTrue(is_full(board))
        self.assertEqual(status(board), X_WINS)

    def test_play(self):
        board = play(EMPTY_BOARD, 4, Cell.X)
        self.assertEqual(to_string(board), "....X....")
        self.assertEqual(to_string(EMPTY_BOARD), ".........")  # original unchanged
        self.assertEqual(legal_moves(board), [0, 1, 2, 3, 5, 6, 7, 8])

    def test_play_rejects_bad_moves(self):
        board = play(EMPTY_BOARD, 4, Cell.X)
        with self.assertRaises(ValueError):
            play(board, 4, Cell.O)
        with self.assertRaises(ValueError):
            play(board, 9, Cell.O)
        with self.assertRaises(ValueError):
            play(board, -1, Cell.O)
        with self.assertRaises(ValueError):
            play(board, 0, Cell.EMPTY)

    def test_other(self):
        self.assertIs(other(Cell.X), Cell.O)
        self.assertIs(other(Cell.O), Cell.X)
        with self.assertRaises(ValueError):
            other(Cell.EMPTY)

    def test_whose_turn(self):
        self.assertIs(whose_turn(EMPTY_BOARD), Cell.X)
        self.assertIs(whose_turn(EMPTY_BOARD, first=Cell.O), Cell.O)
        self.assertIs(whose_turn(from_string("X........")), Cell.O)
        self.assertIs(whose_turn(from_string("O........"), first=Cell.O), Cell.X)
        with self.assertRaises(ValueError):
            whose_turn(from_string("XX......."))
        with self.assertRaises(ValueError):
            whose_turn(from_string("O........"))  # X was supposed to start

    def test_string_round_trip(self):
        for text in (".........", "X.O......", "XOXOXOOXO"):
            self.assertEqual(to_string(from_string(text)), text)
        self.assertEqual(from_string("x o|...|--O"), from_string("X.O|...|..O"))
        with self.assertRaises(ValueError):
            from_string("X.O")
        with self.assertRaises(ValueError):
            from_string("X.O.....Z")

    def test_cell_values(self):
        self.assertEqual(Cell("X"), Cell.X)
        self.assertEqual(Cell(" "), Cell.EMPTY)
        self.assertEqual(str(Cell.O), "O")

    def test_drawer_cell_numbering(self):
        self.assertEqual([to_cell(i) for i in range(9)], list(range(1, 10)))
        self.assertEqual([from_cell(c) for c in range(1, 10)], list(range(9)))


if __name__ == "__main__":
    unittest.main()
