import sys
import os
from datetime import datetime

# Thêm đường dẫn để nhận diện module tools
sys.path.append(os.getcwd())

from tools.database import engine, SessionLocal
from tools.models import Base, Category, Product, Inventory, Customer, Order, OrderItem

def seed_data():
    print("🚀 Đang khởi tạo Database và Seeding dữ liệu...")

    # 1. Reset Database
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    try:
        # 2. Tạo Categories
        camping = Category(name="Đồ cắm trại", description="Lều, túi ngủ và phụ kiện outdoor")
        hiking = Category(name="Leo núi", description="Giày, gậy leo núi và trang bị bảo hộ")
        fashion = Category(name="Thời trang", description="Quần áo thể thao và dã ngoại")

        db.add_all([camping, hiking, fashion])
        db.commit()

        # 3. Tạo Products & Inventory
        products_data = [
            {"name": "Lều cắm trại 4 người", "sku": "CAMP-001", "price": 1200000, "cat": camping, "qty": 15},
            {"name": "Túi ngủ giữ nhiệt", "sku": "CAMP-002", "price": 450000, "cat": camping, "qty": 30},
            {"name": "Giày leo núi chống nước", "sku": "HIKE-001", "price": 2500000, "cat": hiking, "qty": 10},
            {"name": "Balo trợ lực 50L", "sku": "HIKE-002", "price": 1800000, "cat": hiking, "qty": 5},
            {"name": "Áo khoác gió dã ngoại", "sku": "FASH-001", "price": 650000, "cat": fashion, "qty": 50},
        ]

        prods = {}
        for item in products_data:
            new_prod = Product(
                name=item["name"],
                sku=item["sku"],
                price=item["price"],
                category_id=item["cat"].id
            )
            db.add(new_prod)
            db.flush()
            prods[item["sku"]] = new_prod

            new_inv = Inventory(
                product_id=new_prod.id,
                quantity=item["qty"],
                location="Kho A"
            )
            db.add(new_inv)

        # 4. Tạo Customers
        user_phu = Customer(name="Phú Đặng", email="phu@example.com", address="Quận 1, TP.HCM")
        user_lan = Customer(name="Lan Nguyễn", email="lan@example.com", address="Quận 7, TP.HCM")
        db.add_all([user_phu, user_lan])
        db.flush()

        # 5. Tạo Orders
        order1 = Order(customer_id=user_phu.id, status="SHIPPED", total_price=1650000)
        db.add(order1)
        db.flush()

        db.add(OrderItem(order_id=order1.id, product_id=prods["CAMP-001"].id, quantity=1, price_at_order=1200000))
        db.add(OrderItem(order_id=order1.id, product_id=prods["CAMP-002"].id, quantity=1, price_at_order=450000))

        order2 = Order(customer_id=user_lan.id, status="PENDING", total_price=2500000)
        db.add(order2)
        db.flush()
        db.add(OrderItem(order_id=order2.id, product_id=prods["HIKE-001"].id, quantity=1, price_at_order=2500000))

        db.commit()
        print("✅ Seeding hoàn tất! Agent đã có dữ liệu Enterprise (Products, Inventory, Orders, Customers).")

    except Exception as e:
        db.rollback()
        print(f"❌ Lỗi Seeding: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()
