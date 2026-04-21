# AGENTIC CORE v3.5 | Enterprise AI Operating System

**Agentic Core** là một hệ thống AI điều hành doanh nghiệp thế hệ mới, được xây dựng trên kiến trúc **Agentic Operational Workflow (V4)**. Hệ thống cho phép tự động hóa các tác vụ phức tạp trong quản lý kho, bán hàng và chăm sóc khách hàng thông qua các Agent tự trị.

---

## Tài liệu tham khảo

- **Lý thuyết Framework**: [AGENTIC-AI-FRAMEWORK (Notion)](https://www.notion.so/AGENTIC-AI-FRAMEWORK-348f2ac486d180509668fd4f75487845)

---

## 📊 Sơ đồ hoạt động (System Flow)

```mermaid
graph LR
    User((Người dùng)) --> API[FastAPI]
    API --> Orch{Orchestrator}

    subgraph Core [🧠 Cognitive Cycle]
        direction TB
        Orch --> Perc[Perception]
        Perc --> Brain[Brain / Reasoning]
        Brain --> Act[Action Node]
        Act --> Eval[Evaluator]
        Eval -->|Chưa đạt| Brain
    end

    subgraph Data [💾 Knowledge & Storage]
        direction TB
        RAG[(Vector Store)]
        Mem[(Episodic Memory)]
        DB[(PostgreSQL)]
    end

    Brain --- RAG
    Brain --- Mem
    Act --- DB
    Eval -->|Hoàn tất| Final[Kết quả]
    Final --> User

    style Core fill:#f9f9f9,stroke:#333,stroke-width:2px
    style Data fill:#e1f5fe,stroke:#01579b,stroke-width:2px
```

---

## 📄 Mô tả Hệ thống (Detailed Description)

Hệ thống **Agentic Core** là một giải pháp AI tự hành được thiết kế để xử lý các nghiệp vụ ERP (Quản trị nguồn lực doanh nghiệp) một cách thông minh. Khác với các phần mềm truyền thống dựa trên form nhập liệu, Agentic Core cho phép người dùng giao tiếp bằng ngôn ngữ tự nhiên.

### Khả năng cốt lõi:
- **Tự trị (Autonomous)**: Agent tự tìm kiếm các bảng dữ liệu liên quan mà không cần con người chỉ định.
- **Tiến hóa (Evolution)**: Hệ thống càng dùng nhiều càng thông minh nhờ cơ chế Learning (Vector Store memory).
- **Đa vai trò (Multi-Role)**: Tự động chuyển đổi giữa vai trò **BUYER** (mua hàng/tra cứu) và **ADMIN** (thống kê/quản trị) dựa trên ngữ cảnh câu hỏi.

---

## 🚀 Tính năng nổi bật

- **🧠 Llama 3 Reasoning Engine**: Khả năng suy luận đa bước vượt trội.
- **🔍 Vector ML Semantic Search**: Tìm kiếm Schema và Kinh nghiệm bằng Vector Similarity (Ollama Embeddings).
- **📦 Multi-Domain Support**: Hỗ trợ đầy đủ **Inventory** và **Sales** (Customers, Orders).
- **🖥️ Enterprise Dashboard**: Giao diện Live Stream logs cao cấp.

---

## 🏗️ Cấu trúc Modular (System Modules)

1. **`agent/`**: Lớp nhận thức (Cognition), bao gồm Brain, Orchestrator và các Node xử lý (Perceive, Act, Eval).
2. **`memory/`**: Bộ nhớ Agent, bao gồm Episodic Memory (quá khứ ngắn hạn) và Semantic Memory (Vector RAG).
3. **`storage/`**: Hạ tầng dữ liệu thô, quản lý kết nối PostgreSQL và SQLAlchemy Models.
4. **`infra/`**: Hạ tầng hệ thống, quản lý Config, Policy (RBAC), Context và Domain logic.
5. **`tools/`**: Danh mục các công cụ thực thi (Tools Registry).
6. **`web/`**: Giao diện người dùng (FastAPI Templates).

---

## 🛠️ Stack Công nghệ

- **Backend**: FastAPI, SQLAlchemy.
- **AI**: Ollama (Llama 3), Vector RAG.
- **UI**: TailwindCSS, Glassmorphism design.

---

## 📥 Hướng dẫn khởi chạy

```bash
# 1. Cài đặt dependency
pip install -r requirements.txt

# 2. Thiết lập biến môi trường (Windows PowerShell)
$env:APP_HOST="127.0.0.1"
$env:APP_PORT="8000"
$env:DATABASE_URL="postgresql://postgres:123456@localhost:5432/agentic_store"
$env:OLLAMA_CHAT_MODEL="llama3:latest"
$env:OLLAMA_REASONING_MODEL="gemma3:4b"
$env:OLLAMA_EMBEDDING_MODEL="llama3:latest"

# 3. Seeding dữ liệu
python seed_db.py

# 4. Chạy Server
python main.py
```
Truy cập: **http://127.0.0.1:8000**

---
*Phát triển bởi PHUNH*
