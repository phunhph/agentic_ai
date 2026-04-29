def build_success_card(data):
    return {
        "cardsV2": [{
            "card": {
                "header": {
                    "title": f"✅ Deal: {data.get('name')}",
                    "subtitle": "Đã ghi nhận vào hệ thống CRM"
                },
                "sections": [{
                    "widgets": [
                        {"decoratedText": {"topLabel": "ESTIMATED VALUE", "text": f"<b>${data.get('budget', 0):,}</b>"}},
                        {"decoratedText": {"topLabel": "STATUS CODE", "text": data.get('status', 'Following')}},
                        {"divider": {}},
                        {"decoratedText": {"topLabel": "EXTRACTED NOTES", "text": str(data.get('mixs', {}))}}
                    ]
                }]
            }
        }]
    }