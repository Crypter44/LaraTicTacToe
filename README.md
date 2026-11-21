# TicTacToe with the NEURA LARA 5

The LARA draws a tic-tac-toe grid and X / O symbols on a whiteboard. A RealSense D405 on the arm will photograph the board, a small conv net will tell X, O and empty cells apart, and a game algorithm will choose the robot's moves.

The robot has no force sensor, so the board height is measured by slowly lowering the pen and watching a joint torque for contact. That measurement is the board calibration, and drawing uses it.

## Setup (once)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# make vendor/neurapy and this folder importable from everywhere in the venv (also from tests/)
SITE=$(.venv/bin/python -c "import sysconfig; print(sysconfig.get_paths()['purelib'])")
echo "$PWD/vendor" >  "$SITE/vendor.pth"
echo "$PWD"        >> "$SITE/vendor.pth"
```

`vendor/neurapy` is NEURA's proprietary client. Do not publish it (it is in `.gitignore`).

## Every session

```bash
./connect.sh                  # sets the Mac's address on the USB LAN adapter, checks the robot answers
source .venv/bin/activate
```

On the robot:

1. Release the E-stop and press the white reset button.
2. Open the web GUI at http://192.168.2.13:8080 and press **Power On**.
3. Press **Power On** again after every switch between simulation and the real arm.

Keep the E-stop within reach whenever the real arm moves.

## Calibrate the board

Do this whenever the board or the table moves.

1. Jog the pen (free drive or pendant) to **6–10 mm above the board centre**, not touching.
2. Run the calibration:

```bash
python calibrate_board.py --points 3     # 3 x 3 points, ~5 min, good first check
python calibrate_board.py                # 5 x 5 points, ~10 min
python calibrate_board.py --rotation 0   # board edges parallel to the robot's x/y axes (default: 45°, a diamond)
```

It writes `board_heights.json` and prints the measured heights relative to the centre. Each run overwrites the file; use `--out other.json` to keep an older one.

## Draw

`main.py` always uses the last calibration in `board_heights.json`. The pen does not need to be jogged anywhere first.

```bash
python main.py                    # simulation
python main.py --real             # real arm, asks for 'yes'
python main.py --real --offset 3  # dry run: pen 3 mm above the board, draws nothing
python main.py --real --offset 0.3
```

`--offset` is how far the pen stays above the probed height, in mm. The default is +0.5. Raise it if the pen presses too hard, lower it if lines are faint.

At the prompt:

| Input | Action |
|---|---|
| `g` | draw the grid |
| `x 5`, `o 1` | draw a symbol in a cell |
| `q` | quit |

Cells are numbered 1–9 from the top left, like a phone keypad.

## Camera

The D405 works as a normal webcam; macOS needs camera permission for the terminal or editor you run it from.

```bash
python camera.py                  # one photo -> captures/<time>.png
python camera.py --name board     # captures/board_<time>.png
python camera.py --index 1        # if the RealSense is not found automatically
```

Over a USB 2.0 cable it delivers at most 1280 × 720 at 5 fps.

## Tests and diagnostics

These scripts were used to develop the contact detection. They are useful when the setup changes. All write CSV logs to `logs/`.

```bash
python tests/probe_test.py --repeat 3      # probe one point 3 times; pen 6-10 mm above the board
python tests/probe_test.py --joint 2       # watch another joint's torque (1-6)
python tests/probe_test.py --threshold 5   # less sensitive contact threshold (Nm)
python tests/force_test.py                 # read-only: torques while someone pushes on the pen
python tests/servo_cycle_test.py           # servo on/off cycles in the air; pen >= 30 mm above the board
```

A good `probe_test` result has a spread of about 0.1 mm or less, with no "CONTACT" before the pen reaches the board.

## Files

| File | Purpose |
|---|---|
| `main.py` | interactive drawing |
| `board_drawer.py` | grid and symbol geometry, follows the board height (`CELL_SIZE`, `SYMBOL_SIZE`, `LIFT`, `DRAW_OFFSET`) |
| `calibrate_board.py` | probes the board on a grid, writes `board_heights.json` |
| `height_map.py` | loads the calibration, interpolates the height at any point |
| `probing.py` | contact detection (`Prober`); its docstring lists the rules learned on the real arm |
| `camera.py` | RealSense capture |
| `connect.sh` | network setup for the robot |
| `tests/` | experiments and diagnostics (see above) |
| `vendor/neurapy` | NEURA's robot client (proprietary) |

## Things to know

- **Contact is detected from one joint's torque.** That joint has to actually turn during a vertical descent, otherwise its friction sticks and slips. With the board at z ≈ 38 cm, that is joint 3, the elbow; this is `SIGNAL_JOINT` in `probing.py`. If the board height changes a lot, check it again with `tests/probe_test.py`.
- **The probe descends at 0.5 mm/s.** The arm keeps moving about 1 s after a stop, so faster probing presses the pen further into the board.
- **Re-enabling the servo interface once made the arm jump to an old position.** `probing.py` therefore lifts back into the air under online control before switching it off. Don't remove that step.
- **Open issue** (`ISSUE.md`): odd movements in the first 2–3 cm of each line or symbol.
