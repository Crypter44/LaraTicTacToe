"""Play against the engine in the console, no hardware.

    python -m tictactoe                     # asks who begins; you are O, the robot X
    python -m tictactoe --first player      # skip the question
    python -m tictactoe --human x           # play X instead
    python -m tictactoe --difficulty easy   # or medium, or a mistake probability like 0.5
"""

import argparse

from . import EMPTY_BOARD, ONGOING, Cell, best_move, other, play, render, status


def ask[T](prompt: str, answers: dict[str, T]) -> T | None:
    """Ask until the input is one of `answers` (keys). Returns its value, None on q / end of input."""
    while True:
        try:
            text = input(prompt).strip().lower()
        except (EOFError, KeyboardInterrupt):
            return None
        if text == "q":
            return None
        if text in answers:
            return answers[text]
        print(f"  invalid, expected one of {', '.join(answers)} (q = quit)")


def main():
    parser = argparse.ArgumentParser(description="Play tic-tac-toe against the engine.")
    parser.add_argument("--first", choices=["player", "robot"], help="who begins (default: ask)")
    parser.add_argument("--human", choices=["x", "o"], default="o", help="your symbol (default: o)")
    parser.add_argument("--difficulty", default="perfect", help="perfect, medium, easy, or a probability 0-1")
    args = parser.parse_args()
    try:
        difficulty = float(args.difficulty)
    except ValueError:
        difficulty = args.difficulty

    human = Cell(args.human.upper())
    robot = other(human)
    first = args.first or ask("who begins? (p = player, r = robot): ",
                              {"p": "player", "player": "player", "r": "robot", "robot": "robot"})
    if first is None:
        return

    board, player = EMPTY_BOARD, human if first == "player" else robot
    while status(board) == ONGOING:
        if player is robot:
            idx = best_move(board, robot, difficulty)
            print(f"robot plays {robot.value} {idx}")
        else:
            print(render(board))
            free = {str(i): i for i in range(9) if board[i] is Cell.EMPTY}
            idx = ask(f"your move ({human.value}, free cell 0-8, q = quit): ", free)
            if idx is None:
                return
        board = play(board, idx, player)
        player = other(player)
    print(render(board))
    print(status(board))


if __name__ == "__main__":
    main()
