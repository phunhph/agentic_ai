"""
V3Service — DANN 3.0 Orchestrator.

Kiến trúc Dynamic Agentic Neural Network (DANN) đầy đủ:

  PerceptionNeuron   → Chuẩn hoá tín hiệu đầu vào, phân tích context vai trò
  ReasoningNeuron    → Kích hoạt NeuralBrain (single-pass LLM) + knowledge graph
  ExecutionNeuron    → Biên dịch + thực thi ExecutionPlan qua SQLAlchemy
  CriticNeuron       → Textual Backpropagation: đánh giá → correction_hint → retry
  SynapticLearner    → Trust Firewall gate → cập nhật NeuralWeightMatrix

Luồng dữ liệu dùng DANNSignal — typed dataclass truyền xuyên suốt các Neuron.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from v3.neural.brain import NeuralBrain
from v3.neural.synapse import SynapseManager
from v3.neural.learning_matrix import NeuralWeightMatrix
from v2.contracts import ExecutionPlan, RequestFilter
from v2.execute import execute_plan
from v2.metadata import MetadataProvider
from infra import settings as cfg

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
#  DANN SIGNAL  — xương sống truyền dữ liệu giữa các Neuron
# ══════════════════════════════════════════════════════════════

@dataclass
class DANNSignal:
    """
    Tín hiệu thần kinh truyền qua toàn bộ pipeline DANN.
    Mỗi Neuron nhận, xử lý, và trả về signal đã bổ sung.
    """
    # ── Input gốc ──────────────────────────────────────────
    raw_query: str
    session_id: str = "default"
    role: str = "DEFAULT"
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # ── Sau PerceptionNeuron ────────────────────────────────
    normalized_query: str = ""
    keywords: list[str] = field(default_factory=list)
    intent: str = "retrieve"          # retrieve | analyze
    confidence: float = 0.0
    tactical_context: dict = field(default_factory=lambda: {
        "role": "DEFAULT",
        "experience_level": "default",
        "tone": "neutral",
        "risk_posture": "balanced",
        "response_style": "neutral",
    })

    # ── Sau ReasoningNeuron ─────────────────────────────────
    primary_entity: str = ""          # hbl_account, hbl_contract, ...
    filters: list[dict] = field(default_factory=list)
    aggregate_ops: list[dict] = field(default_factory=list)
    thought: str = ""
    schema_graph: dict = field(default_factory=dict)
    conclusion_template: str = ""

    # ── Sau ExecutionNeuron ─────────────────────────────────
    data: list[dict] = field(default_factory=list)
    execution_ok: bool = False
    execution_trace: dict = field(default_factory=dict)
    row_count: int = 0

    # ── Sau CriticNeuron (Textual Backpropagation) ──────────
    critique: str = "PENDING"
    needs_retry: bool = False
    retry_count: int = 0
    max_retries: int = 2
    correction_hint: str = ""

    # ── Sau SynapticLearner ─────────────────────────────────
    firewall_decision: str = ""       # allow | quarantine | reject
    firewall_scores: dict = field(default_factory=dict)
    learned: bool = False

    # ── Output tổng hợp ─────────────────────────────────────
    assistant_response: str = ""
    latency_ms: int = 0
    errors: list[str] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════
#  BASE NEURON
# ══════════════════════════════════════════════════════════════

class BaseNeuron:
    name: str = "BaseNeuron"

    def fire(self, signal: DANNSignal) -> DANNSignal:
        raise NotImplementedError

    def _log(self, msg: str, level: str = "debug"):
        getattr(logger, level)(f"[{self.name}] {msg}")


# ══════════════════════════════════════════════════════════════
#  NEURON 1 — PerceptionNeuron
#  Nhận tín hiệu thô → chuẩn hoá → phân loại intent + persona
# ══════════════════════════════════════════════════════════════

class PerceptionNeuron(BaseNeuron):
    """
    Lớp cảm nhận đầu vào (Input Layer).
    Rule-based, không gọi LLM — tiết kiệm latency cho bước đầu.
    Tích hợp tactical_context từ role/session để định hướng reasoning.
    """
    name = "PerceptionNeuron"

    _ANALYZE_SIGNALS = {
        "thống kê", "phân tích", "tổng", "count", "analyze",
        "so sánh", "ranking", "xếp hạng", "đếm", "bao nhiêu",
    }
    _RETRIEVE_SIGNALS = {
        "tìm", "liệt kê", "danh sách", "list", "xem", "lấy",
        "show", "chi tiết", "detail", "hiện",
    }
    _EXPERIENCE_HINTS = {
        "DEFAULT": "default",
        "SENIOR": "senior",
        "JUNIOR": "junior",
        "CEO": "senior",
    }

    def fire(self, signal: DANNSignal) -> DANNSignal:
        self._log(f"query={signal.raw_query!r} role={signal.role}")

        q = signal.raw_query.strip()
        q_lower = q.lower()

        signal.normalized_query = q_lower
        signal.keywords = q_lower.split()

        # Intent classification
        if any(kw in q_lower for kw in self._ANALYZE_SIGNALS):
            signal.intent = "analyze"
            signal.confidence = 0.85
        else:
            signal.intent = "retrieve"
            signal.confidence = 0.75

        # Cập nhật tactical_context từ role
        exp = self._EXPERIENCE_HINTS.get(signal.role.upper(), "default")
        signal.tactical_context = {
            "role": signal.role,
            "experience_level": exp,
            "tone": "professional" if exp == "senior" else "neutral",
            "risk_posture": "balanced",
            "response_style": "strategic" if exp == "senior" else "neutral",
        }

        # --- Clarification flow for ambiguous person-name queries ---
        # Detect patterns like "thông tin sale phunh" or "info sale <token>"
        m = re.search(r"\b(sale|sales|seller|người bán|sale:?)\b\s*(\w[\w.-]{1,40})?$", q_lower)
        if m:
            candidate = m.group(2)
            if candidate:
                # mark that we should clarify before doing full pipeline
                signal.tactical_context["clarify_person"] = {
                    "candidate": candidate,
                    "asked": False,
                }
                # reduce confidence so downstream knows query was ambiguous
                signal.confidence = min(signal.confidence, 0.6)

        self._log(f"intent={signal.intent} exp_level={exp} confidence={signal.confidence}")
        return signal


# ══════════════════════════════════════════════════════════════
#  NEURON 2 — ReasoningNeuron
#  Hidden Layer: kích hoạt NeuralBrain với schema graph + weights
#  Nhận correction_hint từ CriticNeuron nếu đang retry
# ══════════════════════════════════════════════════════════════

class ReasoningNeuron(BaseNeuron):
    """
    Lớp suy luận trung tâm (Hidden Layer).
    Kết nối NeuralBrain ↔ SynapseManager ↔ NeuralWeightMatrix.
    Khi retry: gắn correction_hint vào prompt để LLM tự hiệu chỉnh.
    """
    name = "ReasoningNeuron"

    def __init__(self, brain: NeuralBrain, synapse: SynapseManager, matrix: NeuralWeightMatrix):
        self.brain = brain
        self.synapse = synapse
        self.matrix = matrix

    def fire(self, signal: DANNSignal) -> DANNSignal:
        self._log(f"retry={signal.retry_count} hint={bool(signal.correction_hint)}")

        weights = self.matrix.get_weights()

        # Lấy sub-graph liên quan — không dump toàn bộ schema
        signal.schema_graph = self.synapse.get_local_network(signal.keywords, weights)

        # Xây prompt: gắn correction_hint nếu đang retry
        effective_query = signal.normalized_query
        if signal.correction_hint:
            effective_query = (
                f"{signal.normalized_query}\n\n"
                f"[DANN CORRECTION từ lần kích hoạt trước]: {signal.correction_hint}"
            )

        activation = self.brain.activate(effective_query, signal.schema_graph, weights)

        # Cập nhật signal từ LLM output
        signal.primary_entity = activation.get("primary_entity", "hbl_account")
        signal.filters = activation.get("filters", [])
        signal.thought = activation.get("thought", "")
        signal.conclusion_template = activation.get("conclusion_template", "")

        # LLM có thể override intent nếu cần
        llm_intent = activation.get("intent")
        if llm_intent in {"retrieve", "analyze"}:
            signal.intent = llm_intent

        # Aggregate ops theo intent
        if signal.intent == "analyze":
            signal.aggregate_ops = [{
                "type": "count",
                "table": signal.primary_entity,
                "alias": "total_count",
            }]
        else:
            signal.aggregate_ops = []

        self._log(f"entity={signal.primary_entity} filters={len(signal.filters)} intent={signal.intent}")
        return signal


# ══════════════════════════════════════════════════════════════
#  NEURON 3 — ExecutionNeuron
#  Biên dịch ExecutionPlan → thực thi SQLAlchemy → trả về data
# ══════════════════════════════════════════════════════════════

class ExecutionNeuron(BaseNeuron):
    """
    Lớp thực thi (Action Layer).
    Tự động prefix field, inject tactical_context vào plan.
    """
    name = "ExecutionNeuron"

    def fire(self, signal: DANNSignal) -> DANNSignal:
        self._log(f"entity={signal.primary_entity} filters={signal.filters}")

        try:
            plan = self._compile_plan(signal)
            exec_result = execute_plan(plan)

            signal.data = exec_result.data if hasattr(exec_result, "data") else []

            # Khi intent=analyze, SQL COUNT trả về [{"total_count": N}]
            # → row_count phải là N chứ không phải len(data)==1
            if signal.intent == "analyze" and signal.data:
                first = signal.data[0] if isinstance(signal.data[0], dict) else {}
                agg_val = first.get("total_count")
                if agg_val is not None:
                    signal.row_count = int(agg_val)
                else:
                    signal.row_count = len(signal.data)
            else:
                signal.row_count = len(signal.data)

            signal.execution_ok = True
            signal.execution_trace = getattr(exec_result, "execution_trace", {})

        except Exception as exc:
            signal.execution_ok = False
            signal.row_count = 0
            signal.data = []
            err = f"ExecutionNeuron: {exc}"
            signal.errors.append(err)
            self._log(err, level="warning")

        self._log(f"ok={signal.execution_ok} rows={signal.row_count}")
        return signal

    def _compile_plan(self, signal: DANNSignal) -> ExecutionPlan:
        entity = signal.primary_entity

        # Build RequestFilter list — auto-prefix field với table name
        where_filters: list[RequestFilter] = []
        for f in signal.filters:
            if not isinstance(f, dict):
                continue
            field_name = f.get("field")
            if not field_name:
                continue
            if "." not in field_name:
                field_name = f"{entity}.{field_name}"
            where_filters.append(RequestFilter(
                field=field_name,
                op=f.get("op", "eq"),
                value=f.get("value"),
            ))

        return ExecutionPlan(
            root_table=entity,
            where_filters=where_filters,
            aggregate_ops=signal.aggregate_ops,
            limit=20,
            tactical_context=signal.tactical_context,
        )


# ══════════════════════════════════════════════════════════════
#  NEURON 4 — CriticNeuron  (Textual Backpropagation)
#  Đánh giá output → nếu kém → sinh correction_hint → retry
# ══════════════════════════════════════════════════════════════

class CriticNeuron(BaseNeuron):
    """
    Cơ chế Textual Backpropagation của DANN.

    Không gọi LLM — rule-based heuristics đủ nhanh và đủ chính xác
    để phán xét 3 trường hợp lỗi phổ biến nhất từ lesson_log:

      1. Execution failed (lỗi runtime)
      2. Có filter eq nhưng kết quả rỗng → filter sai giá trị
      3. Analyze rỗng → thử fallback về retrieve
    """
    name = "CriticNeuron"

    def fire(self, signal: DANNSignal) -> DANNSignal:
        self._log(f"rows={signal.row_count} ok={signal.execution_ok} retry={signal.retry_count}")

        if not signal.execution_ok:
            return self._backprop_execution_failure(signal)

        if signal.row_count == 0 and signal.filters:
            return self._backprop_empty_with_filters(signal)

        if signal.row_count == 0 and signal.intent == "analyze":
            return self._backprop_empty_analyze(signal)

        # Kết quả chấp nhận được
        signal.critique = "PASS"
        signal.needs_retry = False
        self._log("critique=PASS")
        return signal

    # ── Backpropagation cases ───────────────────────────────

    def _backprop_execution_failure(self, signal: DANNSignal) -> DANNSignal:
        if signal.retry_count >= signal.max_retries:
            signal.needs_retry = False
            signal.critique = "MAX_RETRY:execution_failed"
            return signal
        signal.needs_retry = True
        signal.retry_count += 1
        last_err = signal.errors[-1] if signal.errors else "unknown"
        signal.correction_hint = (
            f"Lần trước thực thi thất bại: {last_err}. "
            "Hãy chọn entity và filter đơn giản hơn, ưu tiên bảng hbl_account."
        )
        self._log(f"backprop:execution_failure retry={signal.retry_count}")
        return signal

    def _backprop_empty_with_filters(self, signal: DANNSignal) -> DANNSignal:
        if signal.retry_count >= signal.max_retries:
            signal.needs_retry = False
            signal.critique = "MAX_RETRY:empty_with_filters"
            return signal

        eq_filters = [f for f in signal.filters if isinstance(f, dict) and f.get("op") == "eq"]
        if eq_filters:
            bad_fields = [f.get("field", "?").split(".")[-1] for f in eq_filters]
            hint = (
                f"Filter eq trên {bad_fields} trả về rỗng. "
                "Đổi op thành 'contains' hoặc bỏ bớt filter để mở rộng kết quả."
            )
        else:
            hint = (
                "Kết quả rỗng dù có filter. "
                "Kiểm tra lại tên field trong schema, thử bỏ filter để xác nhận dữ liệu tồn tại."
            )

        signal.needs_retry = True
        signal.retry_count += 1
        signal.correction_hint = hint
        signal.filters = []  # Reset để ReasoningNeuron xây lại từ đầu
        self._log(f"backprop:empty_with_filters retry={signal.retry_count}")
        return signal

    def _backprop_empty_analyze(self, signal: DANNSignal) -> DANNSignal:
        if signal.retry_count >= signal.max_retries:
            signal.needs_retry = False
            signal.critique = "MAX_RETRY:empty_analyze"
            return signal

        signal.needs_retry = True
        signal.retry_count += 1
        signal.correction_hint = (
            "Thống kê không có dữ liệu. "
            "Thử chuyển intent='retrieve' và bỏ aggregate_ops để kiểm tra dữ liệu thô."
        )
        self._log(f"backprop:empty_analyze retry={signal.retry_count}")
        return signal


# ══════════════════════════════════════════════════════════════
#  NEURON 5 — SynapticLearner
#  Trust Firewall gate → cập nhật NeuralWeightMatrix
# ══════════════════════════════════════════════════════════════

class SynapticLearner(BaseNeuron):
    """
    Học có kiểm soát (Supervised Reinforcement).

    Trust Firewall đánh giá signal trước khi cho phép ghi vào matrix.
    Giống NFR6/NFR8 trong PRD: chống rote memorization, chống poisoning.
    Chỉ học khi: signal_quality cao + poisoning_risk thấp + không trùng lặp.
    """
    name = "SynapticLearner"

    # Ngưỡng Trust Firewall (align với infra/settings thực tế)
    MIN_SIGNAL_QUALITY = 0.45
    MAX_POISONING_RISK = 0.65
    MAX_PRIVACY_RISK = 0.50

    def __init__(self, matrix: NeuralWeightMatrix):
        self.matrix = matrix

    def fire(self, signal: DANNSignal) -> DANNSignal:
        scores = self._score_signal(signal)
        signal.firewall_scores = scores
        decision = self._gate(scores)
        signal.firewall_decision = decision

        if decision == "allow":
            self._reinforce(signal)
            signal.learned = True
            self._log(f"learned entity={signal.primary_entity} rows={signal.row_count}")
        else:
            self._log(f"firewall={decision} scores={scores}", level="warning")

        return signal

    def _score_signal(self, signal: DANNSignal) -> dict:
        # Signal quality: dựa trên query length và có entity rõ ràng
        has_entity = bool(signal.primary_entity and signal.primary_entity != "hbl_account" or signal.row_count > 0)
        q_len = len(signal.normalized_query.split())
        signal_quality = min(1.0, 0.4 + (0.1 * min(q_len, 6)) + (0.2 if has_entity else 0))

        # Poisoning risk: query quá ngắn hoặc quá nhiều retry
        poisoning_risk = 0.25
        if q_len <= 1:
            poisoning_risk += 0.3
        if signal.retry_count >= 2:
            poisoning_risk += 0.2
        if not signal.execution_ok:
            poisoning_risk += 0.15
        poisoning_risk = min(poisoning_risk, 1.0)

        # Privacy risk: thấp vì đây là internal tool (PRD §5)
        privacy_risk = 0.25

        # Semantic signal: có filter cụ thể và kết quả > 0
        semantic_signal = 1.0 if (signal.filters and signal.row_count > 0) else (
            0.7 if signal.row_count > 0 else 0.4
        )

        return {
            "signal_quality": round(signal_quality, 3),
            "poisoning_risk": round(poisoning_risk, 3),
            "privacy_risk": round(privacy_risk, 3),
            "semantic_signal": round(semantic_signal, 3),
        }

    def _gate(self, scores: dict) -> str:
        if scores["signal_quality"] < self.MIN_SIGNAL_QUALITY:
            return "reject"
        if scores["poisoning_risk"] > self.MAX_POISONING_RISK:
            return "quarantine"
        if scores["privacy_risk"] > self.MAX_PRIVACY_RISK:
            return "quarantine"
        return "allow"

    def _reinforce(self, signal: DANNSignal) -> None:
        success = signal.execution_ok and signal.row_count > 0

        # Reinforce entity path
        self.matrix.reinforce(signal.primary_entity, success=success)

        # Reinforce filter paths — matrix học được field nào hữu ích
        for f in signal.filters:
            if isinstance(f, dict) and f.get("field"):
                field_key = f.get("field", "").split(".")[-1]
                path = f"{signal.primary_entity}.{field_key}"
                self.matrix.reinforce(path, success=success)


# ══════════════════════════════════════════════════════════════
#  OUTPUT SYNTHESIZER  — Tổng hợp response cuối cùng
# ══════════════════════════════════════════════════════════════

class OutputSynthesizer:
    """
    Tổng hợp assistant_response từ conclusion_template của LLM.
    Fallback về template mặc định nếu LLM không trả về gì hữu ích.
    """
    name = "OutputSynthesizer"

    def synthesize(self, signal: DANNSignal) -> str:
        count = signal.row_count
        template = signal.conclusion_template or ""
        templates = getattr(cfg, "RESPONSE_TEMPLATES", {})

        # If template is just the generic 'Dạ, Cindy... {count}...' prefer our nicer phrasing
        use_template = None
        if template and len(template) >= 5:
            if not (template.strip().startswith("Dạ, Cindy") and "{count}" in template):
                try:
                    use_template = re.sub(r"\{.*?\}", str(count), template)
                except Exception:
                    use_template = None

        # Build examples from result rows when available
        examples_text = ""
        if count > 0 and signal.data:
            try:
                provider = MetadataProvider()
                id_field = provider.resolve_identity_field(signal.primary_entity)
            except Exception:
                id_field = None

            examples = []
            for row in signal.data[:3]:
                if isinstance(row, dict):
                    if id_field and id_field in row and row.get(id_field):
                        examples.append(str(row.get(id_field)))
                    else:
                        for key in ("fullname", "name", "displayname", "firstname", "first_name"):
                            if key in row and row.get(key):
                                examples.append(str(row.get(key)))
                                break
            examples = [e.strip() for e in examples if e and str(e).strip()]
            if examples:
                examples_text = "; ".join(examples)

        # Friendly entity labels for clearer sentences
        ENTITY_LABELS = {
            "systemuser": "người bán hàng",
            "hbl_account": "khách hàng",
            "hbl_contract": "hợp đồng",
            "hbl_opportunities": "cơ hội",
        }
        entity_label = ENTITY_LABELS.get(signal.primary_entity, "kết quả")

        # If exactly one row and we have an example name, be specific
        if count == 1 and examples_text:
            name = examples_text.split("; ")[0]
            tpl = templates.get("find_one")
            if tpl:
                return tpl.format(entity_label=entity_label, name=name)
            return f"Dạ, Cindy tìm thấy 1 {entity_label} tên {name}."

        # If multiple rows, include examples summary when available
        if count > 1:
            tpl = templates.get("find_multiple")
            if tpl and examples_text:
                return tpl.format(count=count, entity_label=entity_label, examples=examples_text)
            base = (
                f"Dạ, Cindy đã tìm thấy {count} {entity_label} cho yêu cầu '{signal.raw_query}'."
                if signal.intent != "analyze"
                else f"Dạ, Cindy thống kê được {count} {entity_label} cho yêu cầu '{signal.raw_query}'."
            )
            if examples_text:
                return f"{base} Ví dụ: {examples_text}."
            return base

        # Zero rows
        if count == 0:
            tpl = templates.get("not_found")
            if tpl:
                return tpl.format(entity_label=entity_label, query=signal.raw_query)
            if use_template:
                return use_template
            return f"Dạ, Cindy đã tìm nhưng chưa thấy {entity_label} phù hợp cho '{signal.raw_query}'. Bạn muốn thử từ khoá khác không ạ?"

        # Fallback: use template if it's good, else generic
        if use_template:
            return use_template
        tpl = templates.get("generic_processed")
        if tpl:
            return tpl.format(query=signal.raw_query, count=count)
        return f"Dạ, Cindy đã xử lý yêu cầu '{signal.raw_query}'. Kết quả: {count}."


# ══════════════════════════════════════════════════════════════
#  V3SERVICE  — DANN 3.0 Pipeline Orchestrator
# ══════════════════════════════════════════════════════════════

class V3Service:
    """
    Điều phối pipeline DANN 3.0 với Textual Backpropagation loop.

    Luồng chuẩn (không retry):
      Perception → Reasoning → Execution → Critic → SynapticLearner → Output

    Luồng khi CriticNeuron phát hiện lỗi (needs_retry=True):
      Critic → Reasoning → Execution → Critic  (lặp tối đa max_retries lần)
                ↑                         ↓
                └──── correction_hint ────┘
    """

    def __init__(self):
        # Neural components
        self.brain = NeuralBrain()
        self.synapse = SynapseManager()
        self.matrix = NeuralWeightMatrix()

        # DANN Neurons
        self.perception = PerceptionNeuron()
        self.reasoning = ReasoningNeuron(self.brain, self.synapse, self.matrix)
        self.executor = ExecutionNeuron()
        self.critic = CriticNeuron()
        self.learner = SynapticLearner(self.matrix)
        self.synthesizer = OutputSynthesizer()

    def run(self, query: str, session_id: str = "default", role: str = "DEFAULT") -> dict:
        start = time.time()

        # Khởi tạo DANN Signal
        signal = DANNSignal(
            raw_query=query,
            session_id=session_id,
            role=role,
        )

        # ── Neuron 1: Perception ────────────────────────────
        signal = self.perception.fire(signal)

        # If Perception flagged an ambiguous person-name, ask for clarification now
        clarify = signal.tactical_context.get("clarify_person")
        if clarify and not clarify.get("asked"):
            candidate = clarify.get("candidate")
            tpl = cfg.RESPONSE_TEMPLATES.get("clarify_person_question")
            question = tpl.format(candidate=candidate) if tpl else (
                f"Bạn có thể cho tôi biết họ và tên đầy đủ hoặc email của người bán hàng '{candidate}' được không?"
            )
            signal.assistant_response = question
            # mark asked so repeated calls won't loop
            signal.tactical_context["clarify_person"]["asked"] = True
            signal.latency_ms = int((time.time() - start) * 1000)
            return self._format_result(signal)

        # ── Neuron 2 + 3 + 4: Reasoning → Execution → Critic ─
        signal = self.reasoning.fire(signal)
        signal = self.executor.fire(signal)
        signal = self.critic.fire(signal)

        # ── Textual Backpropagation Loop ─────────────────────
        while signal.needs_retry:
            logger.info(
                f"[DANN Backprop] retry={signal.retry_count}/{signal.max_retries} "
                f"hint={signal.correction_hint!r}"
            )
            signal = self.reasoning.fire(signal)
            signal = self.executor.fire(signal)
            signal = self.critic.fire(signal)

        # ── Neuron 5: Synaptic Learning ──────────────────────
        signal = self.learner.fire(signal)

        # ── Output Synthesis ─────────────────────────────────
        signal.assistant_response = self.synthesizer.synthesize(signal)
        signal.latency_ms = int((time.time() - start) * 1000)

        return self._format_result(signal)

    def run_pipeline(self, goal: str, session_id: str = "", role: str = "DEFAULT") -> dict:
        """Backward-compatible wrapper used by existing callers (CLI / tests / web).

        Returns a dict with `ok`, `assistant_response`, `data`, and a nested
        `reasoning` dict so older code paths keep working.
        """
        # Normalize session_id fallback
        sid = session_id or "default"
        result = self.run(goal, session_id=sid, role=role)

        reasoning = {
            "intent": result.get("intent"),
            "primary_entity": result.get("primary_entity"),
            "thought_process": result.get("thought_process"),
            "critique": result.get("critique"),
            "retry_count": result.get("retry_count", 0),
            "firewall_decision": result.get("firewall_decision"),
            "firewall_scores": result.get("firewall_scores"),
            "latency_ms": result.get("latency_ms"),
        }

        return {
            "ok": True,
            "query": result.get("query"),
            "assistant_response": result.get("assistant_response"),
            "data": result.get("data", []),
            "reasoning": reasoning,
            "latency_ms": result.get("latency_ms"),
        }

    def _format_result(self, signal: DANNSignal) -> dict:
        return {
            "query": signal.raw_query,
            "data": signal.data,
            "assistant_response": signal.assistant_response,
            "resolved_query": signal.normalized_query,
            "intent": signal.intent,
            "primary_entity": signal.primary_entity,
            "thought_process": signal.thought,
            "reflection": signal.thought,
            "execution_result": signal.data,
            "critique": signal.critique,
            "retry_count": signal.retry_count,
            "firewall_decision": signal.firewall_decision,
            "firewall_scores": signal.firewall_scores,
            "latency_ms": signal.latency_ms,
        }
