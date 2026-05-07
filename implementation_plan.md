# Tái Cấu Trúc Dự Án Theo Module Chức Năng Rõ Ràng

## Phân Tích Hiện Trạng

Cấu trúc hiện tại có vấn đề ở chỗ:
- `v2/service.py` — file **"god class"** 1018 dòng, chứa tất cả mọi thứ: helper functions, pipeline logic, response building, i18n, learning
- `main.py` — 335 dòng mix API routes + business logic helpers
- `v2/` có các thư mục module đúng nhưng chưa rõ ràng vai trò từng giai đoạn
- `DANN/` chứa core graph/matrix nhưng bị tách rời khỏi `v2/learn/`
- Không có `shared/` hoặc `core/` cho utilities dùng chung (i18n, formatting)
- `storage/` và `infra/` thiếu rõ ràng mục đích

---

## Cấu Trúc Mục Tiêu

```
agentic_ai/
├── main.py                          # FastAPI app bootstrap (chỉ routes, không logic)
├── requirements.txt
├── .env / .env.example
├── db.json                          # Schema metadata
│
├── core/                            # ⚙️ Shared infrastructure
│   ├── __init__.py
│   ├── settings.py                  # (move từ infra/)
│   ├── database.py                  # (move từ storage/)
│   ├── contracts.py                 # (move từ v2/) - shared dataclasses
│   ├── i18n.py                      # (tách từ service.py) - _t(), _detect_locale()
│   └── formatting.py               # (tách từ service.py) - humanize, clean_token, etc.
│
├── pipeline/                        # 🔄 Agentic Pipeline - 6 giai đoạn rõ ràng
│   ├── __init__.py                  # run_pipeline() - entry point duy nhất
│   │
│   ├── phase1_ingest/               # 📥 Giai đoạn 1: Thu nhận & phân tích đầu vào
│   │   ├── __init__.py
│   │   ├── parser.py                # (move từ v2/ingest/parser.py)
│   │   ├── context_merger.py        # (tách từ service.py) - _apply_context_to_ingest()
│   │   └── pubsub/
│   │       ├── ingress.py           # (move từ v2/ingest/pubsub_ingress.py)
│   │       └── worker.py            # (move từ v2/ingest/pubsub_worker.py)
│   │
│   ├── phase2_reason/               # 🧠 Giai đoạn 2: Suy luận & phân tích ngữ nghĩa
│   │   ├── __init__.py
│   │   ├── core.py                  # (move từ v2/reason/core.py)
│   │   └── consistency.py          # (tách từ service.py) - _validate_reasoning_consistency()
│   │
│   ├── phase3_plan/                 # 📋 Giai đoạn 3: Lập kế hoạch thực thi
│   │   ├── __init__.py
│   │   └── compiler.py              # (move từ v2/plan/compiler.py)
│   │
│   ├── phase4_execute/              # ⚡ Giai đoạn 4: Thực thi kế hoạch
│   │   ├── __init__.py
│   │   ├── runtime.py               # (move từ v2/execute/runtime.py)
│   │   ├── validator.py             # (move từ v2/execute/validator.py)
│   │   └── fk_resolver.py          # (tách từ service.py) - _resolve_fk_labels()
│   │
│   ├── phase5_learn/                # 📚 Giai đoạn 5: Học từ kết quả
│   │   ├── __init__.py
│   │   ├── matrix.py                # (move từ v2/learn/matrix.py)
│   │   ├── graph.py                 # (move từ v2/learn/graph.py)
│   │   ├── loop.py                  # (move từ v2/learn/loop.py)
│   │   ├── trainset.py              # (move từ v2/learn/trainset.py)
│   │   ├── firewall.py              # (move từ v2/learn/firewall.py)
│   │   └── sample_builder.py       # (tách từ service.py) - _build_runtime_learning_sample()
│   │
│   └── phase6_respond/              # 💬 Giai đoạn 6: Tạo phản hồi cho người dùng
│       ├── __init__.py
│       ├── builder.py               # (tách từ service.py) - _build_professional_response()
│       ├── agentic.py               # (tách từ service.py) - _build_agentic_response()
│       └── tactician.py             # (tách từ service.py) - _apply_tactician_layer()
│
├── intelligence/                    # 🧬 DANN - Neural intelligence layer
│   ├── __init__.py
│   ├── neural_matrix.py             # (move từ DANN/core/)
│   ├── agentic_graph.py             # (move từ DANN/core/)
│   └── persona/
│       ├── core.py                  # (move từ v2/tactician/core.py)
│       └── profile.py               # (move từ v2/tactician/persona_profile.py)
│
├── memory/                          # 💾 Bộ nhớ & ngữ cảnh hội thoại
│   ├── __init__.py
│   └── session.py                   # (move từ v2/memory.py)
│
├── metadata/                        # 📊 Metadata schema & provider
│   ├── __init__.py
│   └── provider.py                  # (move từ v2/metadata.py)
│
├── clients/                         # 🌐 LLM & External API clients
│   ├── __init__.py
│   └── llm.py                       # (move từ v2/api_clients.py)
│
├── api/                             # 🚪 HTTP API layer (routes only)
│   ├── __init__.py
│   ├── routes_pipeline.py           # /api/v2/run, /api/v2/diagnose
│   ├── routes_training.py           # /api/v2/train, /api/v2/training/overview
│   ├── routes_events.py             # /api/v2/events/*
│   └── routes_context.py            # /api/v2/contexts/*
│
├── scripts/                         # 🛠️ Dev/ops scripts
│   ├── seed_demo_data.py
│   ├── auto_train_runtime_cases.py
│   └── regression_v2_runtime.py
│
├── storage/                         # 📁 Persisted artifacts (JSON, JSONL)
│   └── v2/
│       ├── matrix/
│       ├── graph/
│       └── training/
│
└── web/                             # 🖥️ Frontend
    └── templates/
        └── v2_console.html
```

---

## Mục Tiêu Chính Của Tái Cấu Trúc

| Vấn đề | Giải pháp |
|--------|-----------|
| `service.py` 1018 dòng "god class" | Tách thành 9 module nhỏ có trách nhiệm rõ ràng |
| Tên thư mục `v2/` không nói lên giai đoạn | Đổi sang `pipeline/phase1_*` ... `phase6_*` |
| Helper functions vương vãi khắp nơi | Gom vào `core/i18n.py` và `core/formatting.py` |
| `DANN/` tách biệt không liên kết | Tích hợp vào `intelligence/` |
| Routes trong `main.py` lẫn với logic | Tách routes ra `api/routes_*.py` |
| `infra/` và `storage/database.py` không rõ | Gom vào `core/` |

---

## Các Bước Thực Hiện

### Bước 1 — Tạo `core/` (shared infrastructure)
- Move `infra/settings.py` → `core/settings.py`  
- Move `storage/database.py` → `core/database.py`
- Move `v2/contracts.py` → `core/contracts.py`
- Tách `_t()`, `_detect_locale()`, `_resolve_locale()` từ `service.py` → `core/i18n.py`
- Tách `_humanize_*`, `_clean_*`, `_format_value()` → `core/formatting.py`

### Bước 2 — Tạo `pipeline/` với 6 phases
- Move toàn bộ `v2/ingest/` → `pipeline/phase1_ingest/`
- Tách `_apply_context_to_ingest()` → `pipeline/phase1_ingest/context_merger.py`
- Move `v2/reason/` → `pipeline/phase2_reason/`
- Tách `_validate_reasoning_consistency()` → `pipeline/phase2_reason/consistency.py`
- Move `v2/plan/` → `pipeline/phase3_plan/`
- Move `v2/execute/` → `pipeline/phase4_execute/`
- Tách `_resolve_fk_labels()` → `pipeline/phase4_execute/fk_resolver.py`
- Move `v2/learn/` → `pipeline/phase5_learn/`
- Tách `_build_runtime_learning_sample()` → `pipeline/phase5_learn/sample_builder.py`
- Tạo `pipeline/phase6_respond/` từ các hàm response builder trong `service.py`

### Bước 3 — Tạo `pipeline/__init__.py` (entry point)
- `run_pipeline()` thay thế `run_v2_pipeline()` với import sạch từ các phase

### Bước 4 — Tạo `intelligence/` cho DANN
- Move `DANN/core/` → `intelligence/`
- Move `v2/tactician/` → `intelligence/persona/`

### Bước 5 — Tạo `api/` routes layer
- Tách `main.py` routes thành 4 file routes theo nhóm chức năng
- `main.py` chỉ còn: app creation + include routers

### Bước 6 — Gom `memory/` và `metadata/` và `clients/`
- Move `v2/memory.py` → `memory/session.py`
- Move `v2/metadata.py` → `metadata/provider.py`
- Move `v2/api_clients.py` → `clients/llm.py`

### Bước 7 — Cập nhật tất cả imports

---

## Open Questions

> [!IMPORTANT]
> **Câu hỏi 1**: Tên thư mục pipeline phase — bạn thích format nào?
> - Option A: `phase1_ingest/`, `phase2_reason/`, ... (rõ thứ tự)
> - Option B: `01_ingest/`, `02_reason/`, ... (đánh số)
> - Option C: Giữ tên cũ `ingest/`, `reason/`, ... nhưng gom vào `pipeline/`

> [!IMPORTANT]
> **Câu hỏi 2**: Phạm vi thực hiện — mình có nên:
> - (A) **Chỉ tái cấu trúc thư mục + cập nhật imports** (an toàn, không thay đổi logic)
> - (B) **Tái cấu trúc + refactor code** (tách god class `service.py` ra nhiều file nhỏ)

> [!WARNING]
> Đây là thay đổi lớn ảnh hưởng đến **tất cả imports** trong dự án. Sau khi thực hiện cần chạy regression test để đảm bảo không broke functionality.

## Verification Plan

### Automated Tests
- Chạy `python -m pytest scripts/regression_v2_runtime.py` sau refactor
- Kiểm tra `python main.py` không có import errors
- Test `/api/v2/run` với câu query mẫu

### Manual Verification
- Mở UI `v2_console.html`, submit query, kiểm tra tất cả 6 giai đoạn hiện đúng trong response layers
