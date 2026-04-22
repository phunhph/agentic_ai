"""Sinh bộ case JSON cho ma trận eval dựa hoàn toàn trên tri thức Metadata."""

from __future__ import annotations
from core.metadata_provider import get_metadata_provider
from dynamic_metadata.tool_inference import infer_best_tool_for_tables

def build_cases() -> list[dict]:
    provider = get_metadata_provider()
    cases: list[dict] = []
    
    # Lấy thông tin động từ tri thức hệ thống
    tables = [t.name for t in provider._schema.tables]
    choice_options = provider._schema.choice_options

    # 1. Tự động sinh Case Truy vấn Bảng (Identity Search)
    # Giúp Agent học cách nhận diện mọi bảng có trong CRM
    for table_name in tables:
        label = provider.get_table_display(table_name) or table_name
        default_tool = infer_best_tool_for_tables([table_name], default_tool="list_accounts")
        cases.append({
            "query": f"Cho tôi xem danh sách {label}",
            "expected_tool": default_tool,
            "expected_entities": [table_name],
        })

    # 2. Tự động sinh Case Quan hệ (Relational Pathfinding)
    # Thử thách Agent tìm đường nối giữa các bảng chính
    main_relations = [
        ("hbl_contract", "hbl_account"),
        ("hbl_opportunities", "hbl_account"),
        ("hbl_contact", "hbl_account")
    ]
    for from_t, to_t in main_relations:
        if from_t in tables and to_t in tables:
            cases.append({
                "query": f"Tìm {from_t} liên quan đến {to_t}",
                "expected_tool": infer_best_tool_for_tables([from_t, to_t], default_tool="list_accounts"),
                "expected_entities": [from_t, to_t],
                # Expected path sẽ được planner tự tính dựa trên Graph tri thức
            })

    # 3. Tự động sinh Case Bộ lọc (Choice Dictionary)
    # Kiểm tra khả năng hiểu mã code (SI, Mega, Vietnam...)
    for group, options in choice_options.items():
        if not options: continue
        
        # Lấy mẫu ngẫu nhiên hoặc vài option đầu tiên để test
        for option in options[:1]: 
            label = option["label"]
            cases.append({
                "query": f"Khách hàng thuộc nhóm {label}",
                "expected_tool": "list_accounts",
                "choice_group": group,
                "choice_label": label,
                "expected_choice_code": option["code"]
            })

    # 4. Tự động sinh Case từ "Kinh nghiệm cũ" (Knowledge Injection)
    # Nếu có dữ liệu từ các lần chat thực tế (như space_messages.json), 
    # ta có thể seed thêm các case có 'knowledge_hits' để test tính tự học.
    cases.append(
        {
            "query": "list contacts",
            "expected_tool": "list_contacts",
            "expected_entities": ["hbl_contact"],
        }
    )

    return cases