"""Professional Google Chat Cards V2 builders following UX spec.

Cards follow data-dense grid pattern, emoji state machine, and one-tap buttons.
"""


def build_success_card_v2(extracted_data: dict) -> dict:
    """Build a success card showing extracted BANT data.
    
    Layout: Header + BANT grid (2 cols) + tactics list + divider + actions.
    """
    name = extracted_data.get('name') or 'Unknown Deal'
    budget = extracted_data.get('budget') or 0
    status = extracted_data.get('status') or 'Following'
    bant_need = extracted_data.get('bant_need') or '(chưa rõ)'
    tactics = extracted_data.get('tactics') or []
    
    widgets = [
        {
            "decoratedText": {
                "topLabel": "DEAL NAME",
                "text": f"<b>{name}</b>"
            }
        },
        {
            "columns": {
                "columnItems": [
                    {
                        "widgets": [
                            {
                                "decoratedText": {
                                    "topLabel": "BUDGET (B)",
                                    "text": f"<b>${budget:,.0f}</b>" if budget else "—"
                                }
                            }
                        ]
                    },
                    {
                        "widgets": [
                            {
                                "decoratedText": {
                                    "topLabel": "STATUS",
                                    "text": status
                                }
                            }
                        ]
                    }
                ]
            }
        },
        {
            "decoratedText": {
                "topLabel": "NEED (N)",
                "text": bant_need
            }
        },
        {"divider": {}}
    ]
    
    # Add tactics as a list
    if tactics:
        tactics_text = "\n".join([f"• {t}" for t in tactics[:3]])  # limit to 3
        widgets.append({
            "decoratedText": {
                "topLabel": "SUGGESTED ACTIONS",
                "text": tactics_text
            }
        })
        widgets.append({"divider": {}})
    
    # Action buttons
    widgets.append({
        "buttonList": {
            "buttons": [
                {
                    "text": "✅ Lưu",
                    "onClick": {
                        "action": {
                            "actionMethodName": "confirm_save",
                            "parameters": [{"key": "deal_id", "value": name}]
                        }
                    }
                },
                {
                    "text": "✏️ Chỉnh sửa",
                    "onClick": {
                        "action": {
                            "actionMethodName": "edit_deal",
                            "parameters": [{"key": "deal_id", "value": name}]
                        }
                    }
                }
            ]
        }
    })
    
    return {
        "cardsV2": [{
            "cardId": "success_card",
            "card": {
                "header": {
                    "title": "✅ Dữ liệu được ghi nhận",
                    "subtitle": f"Cập nhật lúc {__import__('datetime').datetime.now().strftime('%H:%M:%S')}"
                },
                "sections": [{"widgets": widgets}]
            }
        }]
    }


def build_fallback_card_v2(ambiguous_field: str, options: list) -> dict:
    """Build a fallback card for ambiguous input (confidence < 0.85).
    
    Presents one-tap buttons for disambiguation.
    """
    buttons = []
    for opt in options[:4]:  # limit to 4 buttons
        buttons.append({
            "text": opt,
            "onClick": {
                "action": {
                    "actionMethodName": "select_option",
                    "parameters": [
                        {"key": "field", "value": ambiguous_field},
                        {"key": "choice", "value": opt}
                    ]
                }
            }
        })
    
    # Add cancel button
    buttons.append({
        "text": "❌ Hủy",
        "onClick": {
            "action": {"actionMethodName": "cancel"}
        }
    })
    
    return {
        "cardsV2": [{
            "cardId": "fallback_card",
            "card": {
                "header": {
                    "title": "❓ Cần xác nhận",
                    "subtitle": f"Trường: {ambiguous_field}"
                },
                "sections": [{
                    "widgets": [
                        {
                            "textParagraph": {
                                "text": f"Hệ thống tìm thấy nhiều lựa chọn cho <b>{ambiguous_field}</b>. Bạn muốn chọn cái nào?"
                            }
                        },
                        {
                            "buttonList": {"buttons": buttons}
                        }
                    ]
                }]
            }
        }]
    }


def build_query_result_card_v2(query: str, results: list) -> dict:
    """Build a data grid card for query results.
    
    Shows key-value pairs or table-like layout.
    """
    if not results:
        return {
            "cardsV2": [{
                "cardId": "query_empty",
                "card": {
                    "header": {"title": "📭 Không có kết quả"},
                    "sections": [{
                        "widgets": [
                            {"textParagraph": {"text": f"Không tìm thấy kết quả cho: <b>{query}</b>"}}
                        ]
                    }]
                }
            }]
        }
    
    widgets = [
        {
            "textParagraph": {
                "text": f"<b>Kết quả tìm kiếm:</b> {len(results)} mục"
            }
        }
    ]
    
    # Build rows
    for idx, item in enumerate(results[:10]):  # limit to 10
        if isinstance(item, dict):
            text = " | ".join([f"{k}: {v}" for k, v in item.items()])
        else:
            text = str(item)
        widgets.append({
            "decoratedText": {
                "text": text,
                "topLabel": f"#{idx+1}"
            }
        })
    
    return {
        "cardsV2": [{
            "cardId": "query_result",
            "card": {
                "header": {"title": "📊 Kết quả truy vấn"},
                "sections": [{"widgets": widgets}]
            }
        }]
    }


def build_emoji_status_card(emoji: str, message: str) -> dict:
    """Minimal emoji + text status card for state transitions."""
    return {
        "cardsV2": [{
            "cardId": "status_card",
            "card": {
                "sections": [{
                    "widgets": [
                        {
                            "textParagraph": {
                                "text": f"{emoji} {message}"
                            }
                        }
                    ]
                }]
            }
        }]
    }
