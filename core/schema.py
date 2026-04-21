DOMAIN_MAP = {
    "INVENTORY_DOMAIN": ["products", "inventories", "categories"],
    "SALES_DOMAIN": ["orders", "order_items", "customers"],
    "ACCOUNTING_HOME": ["invoices", "payments"]
}

DETAILED_SCHEMA = {
    "products": "Columns: id, sku, name, price, category_id. Relation: categories.id",
    "inventories": "Columns: id, product_id, quantity, location. Relation: products.id",
    "categories": "Columns: id, name, description"
}

def get_relevant_schema(intent_domain: str):
    """Máy học sẽ gọi hàm này để lấy đúng mảnh xương rồng nó cần"""
    tables = DOMAIN_MAP.get(intent_domain, [])
    return {t: DETAILED_SCHEMA[t] for t in tables if t in DETAILED_SCHEMA}
