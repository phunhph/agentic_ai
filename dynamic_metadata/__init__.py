"""Dynamic metadata: ma trận case, matrix gate, planner, bước parse intent đầu vào."""

from dynamic_metadata.eval_runner import run_eval
from dynamic_metadata.matrix_gate import evaluate_matrix_gate
from dynamic_metadata.planner import plan_with_metadata

__all__ = ["plan_with_metadata", "evaluate_matrix_gate", "run_eval"]
