"""
DANN - CardViewEngine
Builds Google Chat Cards V2 JSON from Pydantic models.
Components: BANT_Grid_Widget, Gatekeeper_Resolver_Widget, Audit_Footer_Widget
"""
from __future__ import annotations

from typing import Any, Optional
from uuid import UUID


class CardViewEngine:
    """
    Data-driven UI builder. Converts structured data into Card V2 JSON.
    Never outputs unstructured plain text to client.
    Max payload: 4KB per card.
    """

    MODEL_NAME = "Claude Sonnet 4.6"

    # ─── Low-level widget builders ───────────────────────────────────────────

    @staticmethod
    def _text_paragraph(text: str) -> dict:
        return {"textParagraph": {"text": text}}

    @staticmethod
    def _divider() -> dict:
        return {"divider": {}}

    @staticmethod
    def _button(label: str, action_id: str, payload: dict,
                filled: bool = False, danger: bool = False) -> dict:
        color = None
        if danger:
            color = {"red": 0.85, "green": 0.15, "blue": 0.15, "alpha": 1}
        btn: dict[str, Any] = {
            "text": label,
            "onClick": {
                "action": {
                    "function": action_id,
                    "parameters": [
                        {"key": k, "value": str(v)} for k, v in payload.items()
                    ],
                }
            },
        }
        if filled:
            btn["type"] = "FILLED"
        else:
            btn["type"] = "OUTLINED"
        if color:
            btn["color"] = color
        return btn

    @staticmethod
    def _decorated_text(label: str, value: str, bold_value: bool = False) -> dict:
        text = f"<b>{value}</b>" if bold_value else value
        return {
            "decoratedText": {
                "topLabel": label.upper(),
                "text": text if text else "<i>—</i>",
            }
        }

    # ─── Widget builders ──────────────────────────────────────────────────────

    @classmethod
    def bant_grid_widget(
        cls,
        budget: Optional[str],
        authority: Optional[str],
        need: Optional[str],
        timeline: Optional[str],
        changed_fields: Optional[list[str]] = None,
    ) -> dict:
        """2-column BANT grid. Bold changed fields."""
        changed = set(changed_fields or [])
        return {
            "columns": {
                "columnItems": [
                    {
                        "horizontalSizeStyle": "FILL_AVAILABLE_SPACE",
                        "horizontalAlignment": "START",
                        "widgets": [
                            cls._decorated_text("Budget (B)", budget or "—", "budget" in changed),
                            cls._decorated_text("Need (N)", need or "—", "need" in changed),
                        ],
                    },
                    {
                        "horizontalSizeStyle": "FILL_AVAILABLE_SPACE",
                        "horizontalAlignment": "START",
                        "widgets": [
                            cls._decorated_text("Authority (A)", authority or "—", "authority" in changed),
                            cls._decorated_text("Timeline (T)", timeline or "—", "timeline" in changed),
                        ],
                    },
                ]
            }
        }

    @classmethod
    def gatekeeper_resolver_widget(
        cls,
        question: str,
        options: list[dict],  # [{label, action_id, payload}]
        cancel_label: str = "Hủy cập nhật",
    ) -> list[dict]:
        """Vertical button list for ambiguity resolution"""
        widgets = [cls._text_paragraph(question)]
        buttons = [
            cls._button(o["label"], o["action_id"], o.get("payload", {}), filled=True)
            for o in options
        ]
        buttons.append(
            cls._button(cancel_label, "action_cancel", {}, danger=True)
        )
        widgets.append({"buttonList": {"buttons": buttons}})
        return widgets

    @classmethod
    def audit_footer_widget(cls, confidence: float, model: str = None) -> dict:
        m = model or cls.MODEL_NAME
        conf_pct = f"{confidence * 100:.0f}%"
        return {
            "decoratedText": {
                "text": f"<font color='#9aa0a6'>Model: {m} · Confidence: {conf_pct}</font>",
                "bottomLabel": "DANN · LiteNextgenCRM",
            }
        }

    # ─── Full Card builders ────────────────────────────────────────────────────

    @classmethod
    def build_success_update_card(
        cls,
        account_name: str,
        opportunity_name: Optional[str],
        budget: Optional[str],
        authority: Optional[str],
        need: Optional[str],
        timeline: Optional[str],
        changed_fields: list[str],
        confidence: float,
        message_id: Optional[str] = None,
    ) -> dict:
        """Direction 1: Data-Dense Grid - Success card after CRM update"""
        sections = [
            {
                "widgets": [
                    cls.bant_grid_widget(budget, authority, need, timeline, changed_fields)
                ]
            },
            {
                "widgets": [cls._divider()]
            },
            {
                "widgets": [
                    {
                        "buttonList": {
                            "buttons": [
                                cls._button("Hoàn tác", "action_undo",
                                            {"message_id": message_id or ""}, filled=False),
                                cls._button("Xem chi tiết", "action_view_detail",
                                            {"account_name": account_name}, filled=True),
                            ]
                        }
                    }
                ]
            },
            {
                "widgets": [cls.audit_footer_widget(confidence)]
            },
        ]

        return {
            "cardsV2": [{
                "cardId": f"success_{message_id or 'card'}",
                "card": {
                    "header": {
                        "title": account_name,
                        "subtitle": f"✅ {opportunity_name or 'Opportunity Updated'}",
                        "imageType": "CIRCLE",
                        "imageUrl": "https://fonts.gstatic.com/s/i/googlematerialicons/check_circle/v6/24px.svg",
                        "imageAltText": "Success",
                    },
                    "sections": sections,
                }
            }]
        }

    @classmethod
    def build_fallback_card(
        cls,
        question: str,
        options: list[dict],
        confidence: float,
        context_hint: Optional[str] = None,
    ) -> dict:
        """Direction 2: Fallback (Action First) - Gatekeeper ambiguity resolution"""
        widgets = cls.gatekeeper_resolver_widget(question, options)
        if context_hint:
            widgets.insert(0, cls._text_paragraph(
                f"<font color='#9aa0a6'><i>{context_hint}</i></font>"
            ))
        widgets.append(cls._divider())
        widgets.append(cls.audit_footer_widget(confidence))

        return {
            "cardsV2": [{
                "cardId": "fallback_card",
                "card": {
                    "header": {
                        "title": "❓ Cần làm rõ",
                        "subtitle": f"Confidence: {confidence * 100:.0f}%",
                    },
                    "sections": [{"widgets": widgets}],
                }
            }]
        }

    @classmethod
    def build_pipeline_move_card(
        cls,
        account_name: str,
        prev_stage: str,
        new_stage: str,
        actor: str,
        confidence: float,
        message_id: Optional[str] = None,
    ) -> dict:
        """Direction 3: Linear Timeline - Pipeline stage change"""
        return {
            "cardsV2": [{
                "cardId": f"pipeline_{message_id or 'card'}",
                "card": {
                    "header": {
                        "title": "✅ Pipeline Moved",
                        "subtitle": account_name,
                    },
                    "sections": [
                        {
                            "widgets": [
                                cls._decorated_text("Previous Stage",
                                                    f"<s>{prev_stage}</s>", False),
                                cls._decorated_text("New Stage", new_stage, True),
                                cls._decorated_text("Actor", actor, False),
                            ]
                        },
                        {"widgets": [cls._divider()]},
                        {
                            "widgets": [
                                {
                                    "buttonList": {
                                        "buttons": [
                                            cls._button("Undo Action", "action_undo",
                                                        {"message_id": message_id or ""}, danger=True)
                                        ]
                                    }
                                }
                            ]
                        },
                        {"widgets": [cls.audit_footer_widget(confidence)]},
                    ],
                }
            }]
        }

    @classmethod
    def build_query_result_card(
        cls,
        title: str,
        rows: list[dict[str, str]],
        confidence: float,
        summary: Optional[str] = None,
    ) -> dict:
        """Analyst query result as structured key-value grid"""
        widgets: list[dict] = []
        if summary:
            widgets.append(cls._text_paragraph(f"<b>{summary}</b>"))
            widgets.append(cls._divider())
        for row in rows:
            for k, v in row.items():
                widgets.append(cls._decorated_text(k, v))
        widgets.append(cls._divider())
        widgets.append(cls.audit_footer_widget(confidence))

        return {
            "cardsV2": [{
                "cardId": "query_result",
                "card": {
                    "header": {"title": f"📊 {title}"},
                    "sections": [{"widgets": widgets}],
                }
            }]
        }

    @classmethod
    def build_extraction_tactician_card(
        cls,
        account_name: str,
        stall_reason: str,
        proposed_action: str,
        email_template: Optional[str],
        confidence: float,
    ) -> dict:
        """Phase 4: Extraction Tactician - Deal stall intervention"""
        widgets: list[dict] = [
            cls._text_paragraph(f"<b>⚠️ Deal Stall Detected:</b> {stall_reason}"),
            cls._divider(),
            cls._text_paragraph(f"<b>Đề xuất hành động:</b>\n{proposed_action}"),
        ]
        if email_template:
            widgets.append(cls._text_paragraph(
                f"<b>Template email gợi ý:</b>\n<i>{email_template[:300]}...</i>"
            ))
        widgets.append(cls._divider())
        widgets.append(cls.audit_footer_widget(confidence))

        return {
            "cardsV2": [{
                "cardId": "tactician_card",
                "card": {
                    "header": {
                        "title": "🎯 Extraction Tactician",
                        "subtitle": account_name,
                    },
                    "sections": [{"widgets": widgets}],
                }
            }]
        }

    @classmethod
    def build_error_card(
        cls,
        entity: str,
        message: str,
        fallback_action_label: Optional[str] = None,
    ) -> dict:
        """Zero blank-state: constructive error with escape hatch"""
        widgets: list[dict] = [
            cls._text_paragraph(
                f"Tôi không tìm thấy <b>{entity}</b> nào phù hợp.\n{message}"
            ),
        ]
        buttons = []
        if fallback_action_label:
            buttons.append(cls._button(fallback_action_label, "action_create_new",
                                       {"entity": entity}, filled=True))
        buttons.append(cls._button("Đóng", "action_cancel", {}, danger=False))
        widgets.append({"buttonList": {"buttons": buttons}})

        return {
            "cardsV2": [{
                "cardId": "error_card",
                "card": {
                    "header": {"title": "❌ Không tìm thấy"},
                    "sections": [{"widgets": widgets}],
                }
            }]
        }

    @classmethod
    def build_compass_card(
        cls,
        sender_name: str,
        experience_level: str,
        briefing: str,
        action_items: list[str],
        confidence: float,
    ) -> dict:
        """Daily Tactical Compass - personalized briefing"""
        action_text = "\n".join(f"• {a}" for a in action_items)
        widgets: list[dict] = [
            cls._text_paragraph(f"Chào <b>{sender_name}</b>! 👋"),
            cls._text_paragraph(briefing),
            cls._divider(),
            cls._text_paragraph(f"<b>Hành động hôm nay:</b>\n{action_text}"),
            cls._divider(),
            cls.audit_footer_widget(confidence),
        ]
        return {
            "cardsV2": [{
                "cardId": "compass_card",
                "card": {
                    "header": {
                        "title": "🧭 Daily Compass",
                        "subtitle": f"Level: {experience_level.title()}",
                    },
                    "sections": [{"widgets": widgets}],
                }
            }]
        }


card_engine = CardViewEngine()
