"""
NeuralWeightMatrix — Bộ nhớ trọng số DANN.
Lưu trữ và cập nhật trọng số đường dẫn nơ-ron dựa trên kết quả thực tế.
Hoàn toàn độc lập, không phụ thuộc V2.
"""
import json
from pathlib import Path

WEIGHTS_PATH = Path("storage/dann_weights.json")
DECAY_FACTOR = 0.95  # Mỗi lần load, trọng số cũ giảm 5%


class NeuralWeightMatrix:
    def __init__(self):
        self._weights: dict[str, float] = {}
        self._load()

    def _load(self):
        if not WEIGHTS_PATH.exists():
            self._weights = {}
            return
        try:
            raw = json.loads(WEIGHTS_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                # Weight decay: trọng số cũ mờ dần theo thời gian
                self._weights = {k: v * DECAY_FACTOR for k, v in raw.items() if isinstance(v, (int, float))}
        except Exception:
            self._weights = {}

    def _save(self):
        WEIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        WEIGHTS_PATH.write_text(
            json.dumps(self._weights, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def get_weights(self) -> dict[str, float]:
        """Trả về toàn bộ trọng số hiện tại."""
        return dict(self._weights)

    def get_top_paths(self, limit: int = 5) -> list[tuple[str, float]]:
        """Trả về các đường dẫn nơ-ron mạnh nhất."""
        sorted_paths = sorted(self._weights.items(), key=lambda x: x[1], reverse=True)
        return sorted_paths[:limit]

    def reinforce(self, path: str, success: bool):
        """
        Tăng cường hoặc suy giảm trọng số.
        success=True → +1.0, success=False → -0.5
        """
        delta = 1.0 if success else -0.5
        current = self._weights.get(path, 0.0)
        self._weights[path] = max(current + delta, -5.0)  # Sàn tối thiểu
        self._save()
