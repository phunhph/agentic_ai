from sqlalchemy import func
from tools.database import get_db
from tools.models import Product, Category, Inventory

def search_products(keyword: str):
    db = get_db()
    # Tìm kiếm theo tên sản phẩm hoặc tên danh mục
    results = db.query(Product).join(Category).filter(
        Product.name.ilike(f"%{keyword}%") | Category.name.ilike(f"%{keyword}%")
    ).all()
    
    return [{
        "id": p.id,
        "name": p.name,
        "sku": p.sku,
        "price": p.price,
        "stock": p.inventory.quantity if p.inventory else 0,
        "category": p.category.name
    } for p in results]

def get_inventory_stats():
    db = get_db()
    # Thống kê số lượng sản phẩm theo từng danh mục
    stats = db.query(
        Category.name, 
        func.count(Product.id).label('count')
    ).join(Product).group_by(Category.name).all()
    
    return [{"name": s[0], "stock": s[1]} for s in stats]