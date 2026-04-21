from sqlalchemy import func
from storage.database import get_db
from storage.models import Product, Category, Inventory


def search_products(keyword: str):
    with get_db() as db:
        try:
            # Tìm kiếm kết hợp Category và Product
            results = (
                db.query(Product)
                .join(Category)
                .filter(
                    (Product.name.ilike(f"%{keyword}%"))
                    | (Category.name.ilike(f"%{keyword}%"))
                )
                .all()
            )

            return [
                {
                    "id": p.id,
                    "name": p.name,
                    "price": p.price,
                    "sku": p.sku,
                    "category": p.category.name,
                    "stock": p.inventory.quantity if p.inventory else 0,
                }
                for p in results
            ]
        except Exception:
            return []


def get_inventory_stats():
    with get_db() as db:
        try:
            # Thống kê chuyên sâu cho ADMIN - Sửa lỗi Ambiguous join
            stats = (
                db.query(
                    Category.name,
                    func.count(Product.id).label("total_items"),
                    func.sum(Inventory.quantity).label("total_qty"),
                )
                .join(Product, Category.id == Product.category_id)
                .join(Inventory, Product.id == Inventory.product_id)
                .group_by(Category.name)
                .all()
            )

            return [
                {"category": s[0], "product_count": s[1], "total_quantity": s[2]}
                for s in stats
            ]
        except Exception as e:
            print(f"Lỗi truy vấn stats: {e}")
            return []
