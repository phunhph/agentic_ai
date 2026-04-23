import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from v2.eval import evaluate_feasibility_gate
from v2.learn import evaluate_matrix_v2


def main() -> None:
    eval_report = evaluate_matrix_v2()
    gate = evaluate_feasibility_gate()
    print({"eval_report": eval_report, "gate": gate})


if __name__ == "__main__":
    main()
