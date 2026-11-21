import unittest

from tictactoe import HUMAN_MOVE, INVALID, NO_CHANGE, UNCERTAIN, Cell, from_string, fuse, validate

# robot is X, human is O
KNOWN = from_string("X..|.O.|...")


def check(perceived, confidence=None, **kwargs):
    return validate(KNOWN, from_string(perceived), confidence, human=Cell.O, **kwargs)


def conf(low_cells=(), low=0.4):
    return [low if i in low_cells else 0.95 for i in range(9)]


class ValidateTest(unittest.TestCase):
    def test_no_change(self):
        obs = check("X..|.O.|...")
        self.assertEqual(obs.kind, NO_CHANGE)
        self.assertIsNone(obs.move)

    def test_human_move(self):
        obs = check("X..|.O.|..O", conf())
        self.assertEqual((obs.kind, obs.move), (HUMAN_MOVE, 8))

    def test_human_move_accepts_plain_strings(self):
        obs = validate(KNOWN, ["X", " ", " ", " ", "O", " ", " ", " ", "O"], human=Cell.O)
        self.assertEqual((obs.kind, obs.move), (HUMAN_MOVE, 8))

    def test_two_new_marks(self):
        obs = check("X.O|.O.|..O")
        self.assertEqual(obs.kind, INVALID)
        self.assertIn("2 new marks", obs.detail)

    def test_wrong_symbol(self):
        obs = check("X..|.O.|..X")
        self.assertEqual(obs.kind, INVALID)
        self.assertIn("cell 8", obs.detail)

    def test_human_mark_removed(self):
        obs = check("X..|...|...")
        self.assertEqual(obs.kind, INVALID)
        self.assertIn("cell 4", obs.detail)

    def test_human_mark_changed(self):
        self.assertEqual(check("X..|.X.|...").kind, INVALID)

    def test_low_confidence_on_new_mark(self):
        obs = check("X..|.O.|..O", conf(low_cells=[8]))
        self.assertEqual(obs.kind, UNCERTAIN)
        self.assertIn("cell 8", obs.detail)

    def test_low_confidence_on_empty_cell(self):
        self.assertEqual(check("X..|.O.|...", conf(low_cells=[3])).kind, UNCERTAIN)

    def test_low_confidence_on_changed_human_cell(self):
        self.assertEqual(check("X..|...|...", conf(low_cells=[4])).kind, UNCERTAIN)

    def test_low_confidence_on_unchanged_known_cell_is_fine(self):
        obs = check("X..|.O.|..O", conf(low_cells=[0, 4]))
        self.assertEqual((obs.kind, obs.move), (HUMAN_MOVE, 8))

    def test_confident_error_beats_uncertainty(self):
        self.assertEqual(check("X..|...|..O", conf(low_cells=[3])).kind, INVALID)

    def test_robot_cell_misread_as_empty_is_ignored(self):
        obs = check("...|.O.|..O")
        self.assertEqual((obs.kind, obs.move), (HUMAN_MOVE, 8))
        self.assertIn("cell 0", obs.detail)

    def test_robot_cell_misread_as_empty_with_no_change(self):
        obs = check("...|.O.|...")
        self.assertEqual(obs.kind, NO_CHANGE)
        self.assertIn("cell 0", obs.detail)

    def test_human_symbol_on_robot_cell(self):
        self.assertEqual(check("O..|.O.|...").kind, INVALID)
        obs = check("O..|.O.|...", conf(low_cells=[0]))  # unsure -> robot's own mark is trusted
        self.assertEqual(obs.kind, NO_CHANGE)
        self.assertIn("cell 0", obs.detail)

    def test_min_conf_threshold(self):
        c = conf(low_cells=[8], low=0.7)
        self.assertEqual(check("X..|.O.|..O", c).kind, HUMAN_MOVE)
        self.assertEqual(check("X..|.O.|..O", c, min_conf=0.8).kind, UNCERTAIN)

    def test_human_as_x(self):
        known = from_string("O..|...|...")
        obs = validate(known, from_string("O..|.X.|..."), human=Cell.X)
        self.assertEqual((obs.kind, obs.move), (HUMAN_MOVE, 4))

    def test_bad_lengths(self):
        with self.assertRaises(ValueError):
            validate(KNOWN, [Cell.EMPTY] * 8)
        with self.assertRaises(ValueError):
            validate(KNOWN, KNOWN, [1.0] * 8)


class FuseTest(unittest.TestCase):
    def test_majority_and_confidence(self):
        readings = [from_string("X..|.O.|..O"), from_string("X..|.O.|..."), from_string("X..|.O.|..O"),
                    from_string("X..|.X.|..O")]
        board, confidence = fuse(readings)
        self.assertEqual(board, from_string("X..|.O.|..O"))
        self.assertEqual(confidence[0], 1.0)
        self.assertEqual(confidence[4], 0.75)
        self.assertEqual(confidence[8], 0.75)

    def test_tie_prefers_empty_with_low_confidence(self):
        board, confidence = fuse([from_string("O........"), from_string(".........")])
        self.assertIs(board[0], Cell.EMPTY)
        self.assertEqual(confidence[0], 0.5)

    def test_feeds_validate(self):
        readings = [from_string("X..|.O.|..O")] * 2 + [from_string("X..|.O.|...")] * 2
        board, confidence = fuse(readings)
        self.assertEqual(validate(KNOWN, board, confidence, human=Cell.O).kind, UNCERTAIN)

    def test_single_reading(self):
        board, confidence = fuse([KNOWN])
        self.assertEqual(board, KNOWN)
        self.assertEqual(confidence, (1.0,) * 9)

    def test_bad_input(self):
        with self.assertRaises(ValueError):
            fuse([])
        with self.assertRaises(ValueError):
            fuse([KNOWN, KNOWN[:8]])


if __name__ == "__main__":
    unittest.main()
