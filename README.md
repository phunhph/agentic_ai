# AGENTIC CORE v3.6 | Dynamic Planner + Self-Learning

`Agentic Core` là hệ thống AI vận hành nghiệp vụ theo mô hình `Perceive -> Reason -> Act -> Eval`, đã được nâng cấp với:

- Dynamic metadata planner ưu tiên học từ kinh nghiệm trước.
- Uncertainty manager (`auto_execute`, `ask_clarify`) + trust gate consistency.
- Fast-path + cache để giảm độ trễ planner.
- Matrix learning/eval tự động để theo dõi chất lượng và tiến hóa theo dữ liệu thật.

---

## System Flow (Current - v2 Runtime)

```mermaid
graph LR
    U((User)) --> API[FastAPI]
    API --> P[Ingest Parser]
    P --> R[Reasoner]
    R --> D{Decision State}
    D -->|ask_clarify| C[Clarify Response]
    D -->|auto_execute| PL[Plan Compiler]
    PL --> V[Plan Validator + Trust Gate]
    V -->|trusted| A[Execute Tool]
    V -->|untrusted| C
    A --> T[Persona Tactician]
    T --> E[Learning Trust Firewall + Eval]
    E --> F[Final Payload]
    C --> F
    F --> U
```

## Learning & Correctness Flow

```mermaid
graph TD
    UQ[User Query] --> P1[Ingest: normalize + intent + entities + filters]
    P1 --> P2[Reason + Plan]
    P2 --> D{Decision State}
    D -->|auto_execute| X1[Execute Tool]
    D -->|ask_clarify| X2[Ask Clarify]
    X1 --> V[Validate + Trust Check]
    V --> C{Trusted?}
    C -->|yes| L1[Record outcome + append trainset]
    C -->|no| X2
    X2 --> L2[Return clarify recommendation]
    L1 --> R[Train/Eval matrix report]
    L2 --> R
```

### Lean Flow Spec (ý nghĩa chuẩn)

`Lean flow` trong hệ thống này nghĩa là: **ít bước nhất nhưng vẫn đúng và an toàn**.

Lean hiện tại gồm **2 lớp riêng biệt**:

1. **Lean Decision (luồng quyết định):**
   - Không đủ tín hiệu -> `ask_clarify` (không query DB bừa).
   - Đủ tín hiệu + trust gate pass -> chạy đúng 1 tool chính.
   - Có kết quả hợp lệ -> kết thúc sớm, không loop dư.
   - Sai/mismatch -> ghi tín hiệu học lại, không chồng heuristic nóng.

2. **Lean Personalization (luồng trình bày):**
   - Không đổi logic DB/planner, chỉ đổi khung câu trả lời theo vai trò.
   - `JUNIOR`: thêm hướng dẫn thao tác ngắn, từng bước.
   - `SENIOR`: thêm framing chiến lược, ngắn gọn.
   - `DEFAULT`: giữ trung tính.
   - Code ở: `v2/service.py` -> `_apply_lean_personalization(...)`.
   - Tactician payload ở: `v2/tactician/core.py` -> `build_tactician_payload(...)`.

3. **Reasoning Integrity (tách lớp suy luận và trình bày):**
   - `decision_state` + `execution_plan` được fingerprint riêng (`plan_fingerprint`).
   - Lean/tactician chỉ được phép đổi lớp output text, không đổi core decision.
   - Theo dõi tại `reasoning_integrity` trong payload runtime.

Mục tiêu của lean flow:

- Giảm latency (`p50/p95`).
- Giảm số lần retry loop không tạo giá trị.
- Tăng tỉ lệ đúng ngay lần đầu (`first-pass`).
- Giữ an toàn (không suy diễn khi bằng chứng yếu).

### Correctness checklist (pass/fail)

- `PASS` khi: tool đúng, entity/filter khớp, path/choice đúng, không vi phạm policy/strict.
- `FAIL` khi: tool drift, mismatch entity/filter, reuse lesson sai ngữ cảnh, hoặc execute khi đáng ra phải clarify/block.
- Hệ thống đo liên tục qua:
  - `tool_accuracy`
  - `entity_match_rate`
  - `path_resolution_success`
  - `choice_constraint_success`
  - `strict_block_rate`
  - `decision_state_rate`

## Learning Points In Code (học ở đâu)

Các điểm hệ thống thực sự "học" theo runtime:

1. **Recall tri thức trước khi execute**
   - `v2/service.py` điều phối chuỗi `ingest -> reason -> plan -> execute`.
   - Planner trace nằm trong `planner_trace_v2`.

2. **Học từ kết quả thành công/thất bại**
   - `v2/service.py` gọi `record_outcome(...)`.
   - Runtime sample được append qua `append_trainset_sample(...)`.

3. **Gate kiểm soát độ tin cậy**
   - `validate_execution_plan(...)` chặn sai schema.
   - `_validate_reasoning_consistency(...)` chặn mismatch giữa ingest/reason/plan.

4. **Huấn luyện/eval matrix**
   - `train_matrix_v2()` + `evaluate_matrix_v2()`.
   - Artifacts ở `storage/v2/matrix/*`.

5. **Đánh giá chất lượng học**
   - Snapshot/check nằm trong `learning_check` và `learning_update`.
   - Báo cáo matrix nằm ở `storage/v2/matrix/matrix_v2_eval.json`.
   - Báo cáo firewall nằm ở `storage/v2/firewall/trust_firewall_eval_v2.json`.

6. **Chống học vẹt (Anti-rote)**
   - Dedupe theo `signature` + outcome.
   - Dedupe theo semantic template (`intent + root + query_template`) để bỏ các mẫu chỉ khác câu chữ.
   - Redact dữ liệu literal (query/filter value) trước khi ghi trainset/log.

## Input -> Analysis -> Decision -> Verification (đặc tả rõ)

1. **Input acceptance**
   - Chuẩn hóa query và role/domain ở `v2/ingest/parser.py`.
   - Trích xuất `intent`, `entities`, `request_filters`, `update_data`, `ambiguity_score`.

2. **Analysis**
   - `v2/reason/core.py` tạo planner trace + chọn tool.
   - `v2/plan/compiler.py` chuẩn hóa root/filter theo metadata.

3. **Decision**
   - Runtime trả:
     - `tool`, `args`
     - `decision_state`
     - `trust_gate` (validation + consistency)

4. **Verification (đúng/sai)**
   - Trusted + execute success/fail đều được ghi outcome để học.
   - Không trusted -> trả clarify theo đúng nguyên nhân (ambiguity/guardrail/thiếu entity).

### Runtime behavior (v2)

1. `Ingest`: `v2/ingest/parser.py` trích xuất intent/entities/filters/update_data + ambiguity.
2. `Reason`: `v2/reason/core.py` chọn tool và decision state (`auto_execute`/`ask_clarify`).
3. `Plan`: `v2/plan/compiler.py` chuẩn hóa field/filter theo metadata.
4. `Validate + Trust`: `v2/execute/validator.py` + consistency gate trong `v2/service.py`.
5. `Execute`: `v2/execute/runtime.py` query/update DB.
6. `Respond`: `v2/service.py` dựng response chuyên nghiệp + áp Persona Tactician + Lean Personalization.
7. `Learn`: qua Trust Firewall (`allow/quarantine/reject`) rồi mới `record_outcome`, `append_trainset_sample`, `train_matrix_v2`, `evaluate_matrix_v2`.

### Event lifecycle (Pub/Sub-style)

- Ingress endpoint: `POST /api/v2/events/publish` trả ack nhanh và tạo lifecycle status.
- Event status endpoint: `GET /api/v2/events/{event_id}`.
- Lifecycle state map:
  - `queued` -> `⏳`
  - `analyzing` -> `📊`
  - `processing` -> `🛠️`
  - `done` -> `✅`
  - `clarify` -> `❓`
  - `error` -> `❌`
- SLA điều chỉnh qua `EVENT_ACK_SLA_MS` (mặc định 1500ms).

---

## Planner Enhancements (v3.6)

- **Fast path**: bypass scoring khi intent rõ/tín hiệu đủ.
- **Planner cache**: cache cục bộ cho `match_case`, `extract_entities`, `find_paths`.
- **Adaptive uncertainty calibration**:
  - `calibrated_evidence_floor` được điều chỉnh theo `knowledge score` và `case_success_ratio`.
- **Governance guardrails**:
  - `complexity_score`
  - `PLANNER_COMPLEXITY_BUDGET`
  - cờ `complexity_budget_exceeded`.

---

## Evaluation Metrics (Matrix Report)

File báo cáo: `storage/v2/matrix/matrix_v2_eval.json`

Các metric chính:

- `tool_accuracy`
- `path_resolution_success`
- `choice_constraint_success`
- `entity_match_rate`
- `strict_block_rate`
- `decision_state_rate` (`auto_execute` / `ask_clarify`)
- `decision_reason_distribution`
- `avg_calibrated_evidence_floor`
- `latency_ms` (`mean`, `p50`, `p95`)

Chạy eval:

```bash
python scripts/eval_dynamic_cases.py
```

---

## Key Configuration

Trong `infra/settings.py`:

- `ENABLE_DYNAMIC_METADATA_PLANNER`
- `STRICT_LEARNED_ONLY_MODE`
- `STRICT_MIN_EVIDENCE_SIMILARITY`
- `UNCERTAINTY_BASE_ASK_CLARIFY_EVIDENCE`
- `UNCERTAINTY_LEARNING_SCORE_BONUS_MAX`
- `UNCERTAINTY_CASE_SUCCESS_BONUS_MAX`
- `PLANNER_COMPLEXITY_BUDGET`
- `MATRIX_CASE_MIN_SIMILARITY`
- `MATRIX_CASE_PRIOR_WEIGHT`
- `EVENT_ACK_SLA_MS`

---

## Quick Start

```bash
pip install -r requirements.txt
python seed_db.py
python main.py
```

Truy cập: `http://127.0.0.1:8000`

## Regression check

```bash
python scripts/regression_v2_runtime.py
```

Bao gồm kiểm tra:
- detail/follow-up flow
- event lifecycle ack
- tactician + firewall
- reasoning vs lean integrity
