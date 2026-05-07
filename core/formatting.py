from decimal import Decimal

def _format_value(value):
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "__str__") and "UUID" in str(type(value)):
        return str(value)
    return value

def _clean_table_token(table_name: str) -> str:
    token = str(table_name or "").strip().lower()
    for prefix in ("hbl_", "cr987_", "mc_", "tbl_"):
        if token.startswith(prefix):
            token = token[len(prefix) :]
    return token.strip("_")


def _clean_field_token(field_name: str) -> str:
    token = str(field_name or "").strip().lower()
    for prefix in ("hbl_", "cr987_", "mc_"):
        if token.startswith(prefix):
            token = token[len(prefix) :]
    token = token.strip("_")
    if token.endswith("_id"):
        token = token[:-3]
    elif token.endswith("id"):
        token = token[:-2].rstrip("_")
    return token


def _humanize_words(text: str) -> str:
    words = [w for w in str(text or "").replace("_", " ").split() if w]
    return " ".join(w.capitalize() for w in words)


def _humanize_field_key(raw_key: str, locale: str = "vi") -> str:
    key = str(raw_key or "").strip()
    if not key:
        return "Field" if locale == "en" else "Trường dữ liệu"
    business_labels_vi = {
        "hbl_account_name": "Tên account",
        "hbl_account_physical_address": "Địa chỉ",
        "hbl_account_phone": "Số điện thoại",
        "hbl_account_email": "Email",
        "hbl_account_owner": "Người phụ trách",
    }
    business_labels_en = {
        "hbl_account_name": "Account Name",
        "hbl_account_physical_address": "Address",
        "hbl_account_phone": "Phone",
        "hbl_account_email": "Email",
        "hbl_account_owner": "Owner",
    }
    direct_key = key.split(".", 1)[1] if "." in key else key
    labels = business_labels_en if locale == "en" else business_labels_vi
    if direct_key in labels:
        return labels[direct_key]

    # Joined/derived fields: <table>__<field>
    if "__" in key:
        table_name, field_name = key.split("__", 1)
        table_label = _humanize_words(_clean_table_token(table_name))
        field_label = _humanize_words(_clean_field_token(field_name))
        if locale == "en":
            return f"{table_label} {field_label}".strip()
        return f"{field_label} ({table_label})".strip()

    # FK label enrichment: <field>_label
    if key.lower().endswith("_label"):
        base = key[:-6]
        base_label = _humanize_words(_clean_field_token(base))
        if locale == "en":
            return base_label or "Related info"
        return base_label or "Thông tin liên quan"

    # Regular field: try strip table prefix if exists
    if "." in key:
        _table_name, field_name = key.split(".", 1)
        return _humanize_words(_clean_field_token(field_name))
    return _humanize_words(_clean_field_token(key))
