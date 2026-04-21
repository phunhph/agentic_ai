# AGENTIC CORE v3.5 | Enterprise AI Operating System

**Agentic Core** là một hệ thống AI điều hành doanh nghiệp thế hệ mới, được xây dựng trên kiến trúc **Agentic Operational Workflow (V4)**. Hệ thống cho phép tự động hóa các tác vụ phức tạp trong quản lý kho, bán hàng và chăm sóc khách hàng thông qua các Agent tự trị.

---

## Tài liệu tham khảo

- **Lý thuyết Framework**: [AGENTIC-AI-FRAMEWORK (Notion)](https://www.notion.so/AGENTIC-AI-FRAMEWORK-348f2ac486d180509668fd4f75487845)

---

## 📊 Sơ đồ hoạt động (System Flow)

```mermaid
graph TD
    User((Người dùng)) --> API[FastAPI Entrypoint]
    API --> Orch{Orchestrator}

    subgraph agent [🧠 Cognitive Core]
        Orch --> Perc[Perception Node]
        Perc --> Brain[Brain / Reasoning]
        Brain --> Act[Action Node]
        Act --> Eval[Evaluator Node]
        Eval -.->|Quay lại| Brain
    end

    subgraph storage [💾 Knowledge & Data]
        RAG[(Vector Store)]
        Mem[(Episodic Memory)]
        DB[(PostgreSQL)]
        Learn{Learning Manager}
    end

    Brain ==> RAG
    Brain ==> Mem
    Act ==> DB
    Act -.->|Ghi nhớ bài học| Learn
    Eval ==>|Hoàn tất| Final[Kết quả cuối]
    Final -.->|Lưu trải nghiệm| Learn
    Learn -.->|Cập nhật tri thức| Mem
    Final --> User

    %% Styling for Dark Mode visibility
    linkStyle default stroke:#fff,stroke-width:2px
    style agent fill:#0a0d14,stroke:#3b82f6,stroke-width:2px,color:#fff
    style storage fill:#0a0d14,stroke:#ef4444,stroke-width:2px,color:#fff
    style API fill:#1e293b,stroke:#fff,stroke-width:1px,color:#fff
    style Orch fill:#1e293b,stroke:#fff,stroke-width:1px,color:#fff
    style Final fill:#1e293b,stroke:#fff,stroke-width:1px,color:#fff
```

### 🧠 Giải thích luồng vận hành (Agentic Workflow):

1.  **Perception (Tiếp nhận)**: Agent nhận câu hỏi từ người dùng thông qua FastAPI, thực hiện chuẩn hóa văn bản và xác định vai trò (`BUYER` hoặc `ADMIN`).
2.  **Reasoning (Suy luận)**:
    *   Sử dụng **Llama 3** để phân tích mục tiêu.
    *   **RAG (Vector Store)**: Tìm kiếm các bảng dữ liệu liên quan trong Database Schema.
    *   **Memory**: Truy xuất các bài học thành công trong quá khứ và lời khuyên từ phiên làm việc hiện tại.
3.  **Action (Hành động)**: Gọi các công cụ (Tools) thực tế như `search_products`, `get_orders` để truy vấn dữ liệu từ PostgreSQL.
4.  **Evaluation (Đánh giá)**:
    *   Kiểm tra kết quả thu được. Nếu đã đủ thông tin, Agent sẽ trả về kết quả cuối cùng.
    *   Nếu chưa đủ (ví dụ: không thấy sản phẩm), Agent sẽ tự động quay lại bước **Reasoning** để lập kế hoạch mới (thử từ khóa khác, tìm bảng khác).

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
