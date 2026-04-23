# AGENTIC CORE v3.6 | Dynamic Planner + Self-Learning

`Agentic Core` là hệ thống AI vận hành nghiệp vụ theo mô hình `Perceive -> Reason -> Act -> Eval`, đã được nâng cấp với:

- Dynamic metadata planner ưu tiên học từ kinh nghiệm trước.
- Uncertainty manager (`auto_execute`, `ask_clarify`, `safe_block`).
- Fast-path + cache để giảm độ trễ planner.
- Matrix learning/eval tự động để theo dõi chất lượng và tiến hóa theo dữ liệu thật.

---

## System Flow (Current)

```mermaid
graph LR
    U((User)) --> API[FastAPI]
    API --> O[AgentOrchestrator]
    O --> P[Perception]
    P --> R[Dynamic Planner]
    R --> D{Decision State}
    D -->|auto_execute| A[Action Tool]
    D -->|ask_clarify| C[Clarify Response]
    D -->|safe_block| B[Safe Block]
    A --> E[Evaluator]
    E -->|retry| R
    E -->|done| F[Final Payload]
    C --> F
    B --> F
    F --> U
```

## Learning & Correctness Flow

```mermaid
graph TD
    UQ[User Query] --> P1[Perception: normalize + intent + entities]
    P1 --> P2[Planner: learning-first + metadata reasoning]
    P2 --> D{Decision State}
    D -->|auto_execute| X1[Execute Tool]
    D -->|ask_clarify| X2[Ask Clarify]
    D -->|safe_block| X3[Safe Block]
    X1 --> V[Validate Result]
    V --> C{Correct?}
    C -->|yes| L1[Reinforce lesson/case]
    C -->|no| L2[Penalize/Prune + store reject signals]
    X2 --> L3[Wait clarified input]
    X3 --> L3
    L1 --> R[Update metrics report]
    L2 --> R
```

### Lean Flow Spec (ý nghĩa chuẩn)

`Lean flow` trong hệ thống này nghĩa là: **ít bước nhất nhưng vẫn đúng và an toàn**.

- Không đủ tín hiệu -> `ask_clarify` (không query DB bừa).
- Đủ tín hiệu -> chạy đúng 1 tool chính, hạn chế loop không cần thiết.
- Có kết quả hợp lệ -> kết thúc sớm (short-circuit).
- Sai/mismatch -> ghi tín hiệu lỗi để học lại thay vì thêm heuristic phức tạp ngay.

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

1. **Recall tri thức cũ trước khi plan**
   - `agent/orchestrator.py` gọi `find_similar_lessons(...)`.
   - `dynamic_metadata/planner.py` nhận `knowledge_hits` để reuse nếu tương thích.

2. **Học từ kết quả action thành công/thất bại**
   - `agent/orchestrator.py` gọi `mark_lessons_outcome(...)`.
   - DB lesson score/usage được cập nhật ở `storage/repositories/knowledge_repository.py`.

3. **Phạt tri thức sai**
   - Khi entity/filter mismatch: `penalize_lessons(...)` + `prune_low_confidence_lessons(...)`.
   - Tránh lesson kém chất lượng tiếp tục ảnh hưởng quyết định sau.

4. **Học cấp matrix case**
   - `upsert_case_from_run(...)` trong `dynamic_metadata/matrix_learning.py`.
   - Tăng/giảm độ tin cậy case qua `usage_count`, `success_count`, `penalize_case(...)`.

5. **Đánh giá chất lượng học**
   - `refresh_matrix_eval_report()` và `scripts/eval_dynamic_cases.py`.
   - Xuất báo cáo ở `storage/dynamic_eval_report.json`.

## Input -> Analysis -> Decision -> Verification (đặc tả rõ)

1. **Input acceptance**
   - Chuẩn hóa query và role/domain ở `agent/perception.py`.
   - Trích xuất `intent`, `entities`, `request_contract`.

2. **Analysis**
   - Planner chạy theo thứ tự:
     - learning-first reuse,
     - intent fast-path,
     - autonomous metadata scoring fallback.
   - Sinh `trace` để audit quyết định.

3. **Decision**
   - Planner trả:
     - `tool`, `args`
     - `decision_state`
     - `decision_confidence`
     - `decision_reason`

4. **Verification (đúng/sai)**
   - So khớp kết quả với entity/filter và expectation.
   - Nếu sai -> penalty/prune + reject signals.
   - Nếu đúng -> reinforce score + cập nhật case.

### Runtime behavior

1. `Perception`: chuẩn hóa query, trích xuất intent/entity, request contract.
2. `Reason`:
   - Ưu tiên `knowledge_hits` nếu tương thích entity/structure.
   - Nếu không, chạy metadata planner với:
     - intent fast-path,
     - autonomous scoring theo table alias + case memory,
     - join path + choice constraints.
3. `Uncertainty`:
   - `auto_execute`: đi tiếp sang `Action`.
   - `ask_clarify`: dừng DB call, trả câu hỏi làm rõ ngay cho user.
   - `safe_block`: chặn trong strict mode khi thiếu bằng chứng đã học.
4. `Action + Eval`: thực thi tool, đánh giá dữ liệu trả về, cập nhật learning.
5. `Final`: trả `final_payload` gồm `final_result`, `planner_trace`, `selected_tool`, `db_call_executed`.

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

File báo cáo: `storage/dynamic_eval_report.json`

Các metric chính:

- `tool_accuracy`
- `path_resolution_success`
- `choice_constraint_success`
- `entity_match_rate`
- `strict_block_rate`
- `decision_state_rate` (`auto_execute` / `ask_clarify` / `safe_block`)
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

---

## Quick Start

```bash
pip install -r requirements.txt
python seed_db.py
python main.py
```

Truy cập: `http://127.0.0.1:8000`
