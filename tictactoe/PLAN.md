# Tic-tac-toe decision making + board validation

## Context
The LARA 5 will play tic-tac-toe on a whiteboard. Drawing X/O in a 3x3 grid and board calibration
exist elsewhere; a colleague is building the vision step that turns the home-pose RealSense image into
a board state. This piece is the hardware-free "brain": validate what vision reports against the known
game state, pick the robot's move, and detect game end. It must be a pure, unit-testable module the
(future) state machine can call.

## Location
Separate repo **LaraTicTacToe** (next to NeuraArm/NeuraPy). New package `tictactoe/` at its root,
plain Python, stdlib only, `unittest` tests in `tests/` (same style as NeuraArm's `pdraw/`). Adapt to
any existing layout/conventions found in that repo.

- `tictactoe/__init__.py` – re-exports public API
- `tictactoe/board.py` – representation + rules
- `tictactoe/engine.py` – move selection
- `tictactoe/validate.py` – perception vs. known-state reconciliation
- `tests/test_tictactoe_board.py`, `tests/test_tictactoe_engine.py`, `tests/test_tictactoe_validate.py`

## Design

### board.py
- `Cell` enum: `EMPTY, X, O` (`str` values `" "`, `"X"`, `"O"` for easy logging/JSON).
- Board = immutable `tuple[Cell, ...]` of length 9, index `r*3 + c` (row 0 = top as seen by camera —
  document this; it must match the draw command's cell numbering).
- `LINES` (8 winning triples), `winner(board) -> Cell | None`, `is_full`, `legal_moves`,
  `play(board, idx, player) -> board` (raises on occupied), `other(player)`,
  `whose_turn(board, first)`, `status(board) -> "ongoing" | "x_wins" | "o_wins" | "draw"`,
  `winning_line(board)` (so the robot can optionally strike it through).
- `from_string("X.O......")` / `to_string` helpers for tests and logging.

### engine.py
- `negamax(board, player) -> int` with memoization (`functools.lru_cache`; ≤5478 states) and
  depth-adjusted scores (win = 10 − plies, loss = −(10 − plies)) so it wins fast / loses slow.
- `scored_moves(board, player) -> dict[int, int]`.
- `best_move(board, player, difficulty="perfect", rng=None) -> int`
  - `perfect`: random choice among top-scoring moves (variety, still optimal).
  - `medium` / `easy`: with probability ε (e.g. 0.3 / 0.7) pick a random legal move, else optimal.
    Accept a float too, so the operator can tune ε.
  - `rng: random.Random` injectable for deterministic tests.
  - Raises if game already over / no legal moves.

### validate.py
Reconcile a perceived board with the last known board.
- Input: `known: Board`, `perceived: Sequence[Cell]`, optional `confidence: Sequence[float]`,
  `human: Cell`, `min_conf=0.6`.
- Output dataclass `Observation(kind, move=None, detail="")` where `kind` ∈
  - `NO_CHANGE` → human hasn't moved; recapture/wait
  - `HUMAN_MOVE` (with `move` index) → accept
  - `UNCERTAIN` → a cell that differs (or is empty in known) has confidence < min_conf; recapture
  - `INVALID` → >1 new mark, wrong symbol, a known mark changed/disappeared; retry then ask operator
- Robot's own marks are trusted from `known` (vision disagreement on a robot cell is reported in
  `detail` but not fatal unless it's a human-symbol mark there).
- `fuse(readings: list[list[Cell]]) -> (board, confidence)`: per-cell majority vote across several
  captures, confidence = vote share. Helps the colleague's output plug in directly.

### Intended state-machine use (not implemented here, documented in module docstring)
`HOME → CAPTURE (N frames) → fuse → validate → {NO_CHANGE/UNCERTAIN: recapture | INVALID: operator |
HUMAN_MOVE: play}` → check `status` → `best_move` → draw command(cell, symbol) → `play` into known
state → check `status` → HOME.

## Tests
- board: all 8 lines detected, draw detection, `play` on occupied raises, string round-trip.
- engine: takes immediate win; blocks immediate loss; never loses — exhaustively play engine (perfect)
  vs. every possible opponent move sequence, both as X and O, assert no loss; perfect vs. perfect is a
  draw; prefers faster win when two wins exist; seeded rng gives reproducible easy-mode moves; raises
  on finished board.
- validate: each `kind` case incl. mark removed, wrong symbol, two new marks, low confidence,
  robot-cell misread; `fuse` majority and confidence.

## Verification
- `python -m unittest discover tests` (all existing + new tests pass).
- Quick manual check: a small `python -m tictactoe` console loop (human types cell 0–8, engine
  replies, board printed) to play against it without hardware.
