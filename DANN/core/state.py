import threading
from typing import List, Dict


class StateStore:
    def __init__(self):
        self._qna: List[Dict] = []
        self._trace: List[Dict] = []
        self._lock = threading.Lock()

    def add_qna(self, message: str, sender_id: str):
        with self._lock:
            self._qna.append({"message": message, "sender": sender_id})

    def get_qna(self):
        with self._lock:
            return list(self._qna)

    def add_trace(self, source: str, level: str, message: str, payload: dict = None):
        with self._lock:
            self._trace.append({"source": source, "level": level, "message": message, "payload": payload or {}, "ts": __import__('time').time()})

    def get_trace(self):
        with self._lock:
            return list(self._trace)


_GLOBAL_STATE = StateStore()


def get_state():
    return _GLOBAL_STATE
