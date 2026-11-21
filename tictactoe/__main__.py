"""Play against the engine in the console, no hardware.

    python -m tictactoe                     # you are O, robot (X) starts, perfect play
    python -m tictactoe --human x           # you are X and start
    python -m tictactoe --difficulty easy   # or medium, or a mistake probability like 0.5
"""

import argparse

from . import EMPTY_BOARD, ONGOING, Cell, best_move, from_cell, other, play, render, status, to_cell


def main():
    parser = argparse.ArgumentParser(description="Play tic-tac-toe against the engine.")
    parser.add_argument("--human", choices=["x", "o"], default="o", help="your symbol; X starts (default: o)")
    parser.add_argument("--difficulty", default="perfect", help="perfect, medium, easy, or a probability 0-1")
    args = parser.parse_args()
    try:
        difficulty = float(args.difficulty)
    except ValueError:
        difficulty = args.difficulty

    human = Cell(args.human.upper())
    robot = other(human)
    board, player = EMPTY_BOARD, Cell.X
    while status(board) == ONGOING:
        if player is robot:
            idx = best_move(board, robot, difficulty)
            print(f"robot plays {robot.value} {to_cell(idx)}")
        else:
            print(render(board))
            try:
                text = input(f"your move ({human.value}, cell 1-9, q = quit): ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                text = "q"
            if text == "q":
                return
            if text not in list("123456789") or board[from_cell(int(text))] is not Cell.EMPTY:
                print("  invalid, expected a free cell 1-9")
                continue
            idx = from_cell(int(text))
        board = play(board, idx, player)
        player = other(player)
    print(render(board))
    print(status(board))


if __name__ == "__main__":
    main()
