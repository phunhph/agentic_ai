import random
from storage.database import SessionLocal
from storage.models import Category, Product, Inventory, Customer, Order, OrderItem


def _gen_categories(count: int) -> list[tuple[str, str]]:
    category_pool = [
        ("Đồ cắm trại", "Lều, túi ngủ, bếp và phụ kiện outdoor"),
        ("Leo núi", "Giày, gậy trekking, đồ bảo hộ"),
        ("Thời trang", "Trang phục thể thao, dã ngoại"),
        ("Phụ kiện", "Bình nước, đèn pin, dao đa năng"),
        ("Du lịch", "Balo, vali, phụ kiện chuyến đi"),
        ("Sinh tồn", "Dụng cụ khẩn cấp và cứu hộ"),
    ]
    random.shuffle(category_pool)
    return category_pool[:count]


def _gen_product_name(prefix: str) -> str:
    nouns = ["Lều", "Balo", "Giày", "Áo khoác", "Gậy", "Đèn pin", "Bình nước", "Túi ngủ"]
    suffix = ["Pro", "Ultra", "Lite", "X", "Air", "Max", "Trail", "Plus"]
    return f"{random.choice(nouns)} {prefix}-{random.choice(suffix)}"


def _gen_customer_name() -> str:
    first = ["An", "Bình", "Chi", "Dũng", "Hà", "Huy", "Linh", "Minh", "Phú", "Trang", "Tuấn"]
    last = ["Nguyễn", "Trần", "Lê", "Phạm", "Võ", "Đặng", "Hoàng", "Phan"]
    return f"{random.choice(last)} {random.choice(first)}"


def seed_data() -> None:
    random.seed(42)  # deterministic random data for repeatable debug

    db = SessionLocal()
    try:
        # Reset data in child-first order
        db.query(OrderItem).delete()
        db.query(Order).delete()
        db.query(Inventory).delete()
        db.query(Product).delete()
        db.query(Customer).delete()
        db.query(Category).delete()
        db.commit()

        category_specs = _gen_categories(count=4)
        categories = [Category(name=name, description=desc) for name, desc in category_specs]
        db.add_all(categories)
        db.flush()

        products = []
        sku_counter = 1
        for idx, category in enumerate(categories):
            prefix = f"C{idx + 1}"
            product_per_category = random.randint(3, 6)
            for _ in range(product_per_category):
                sku = f"{prefix}-{sku_counter:04d}"
                sku_counter += 1
                product = Product(
                    sku=sku,
                    name=_gen_product_name(prefix),
                    price=random.randint(150_000, 2_500_000),
                    category_id=category.id,
                )
                db.add(product)
                db.flush()
                products.append(product)
                db.add(
                    Inventory(
                        product_id=product.id,
                        quantity=random.randint(0, 80),
                        location=f"Kho {random.choice(['A', 'B', 'C'])}",
                    )
                )

        customers = []
        used_emails = set()
        for _ in range(12):
            name = _gen_customer_name()
            email_local = f"{name.lower().replace(' ', '.')}.{random.randint(100,999)}"
            email = f"{email_local}@example.com"
            while email in used_emails:
                email = f"{email_local}.{random.randint(1,9)}@example.com"
            used_emails.add(email)
            customers.append(
                Customer(
                    name=name,
                    email=email,
                    address=f"Quận {random.randint(1, 12)}, TP.HCM",
                )
            )
        db.add_all(customers)
        db.flush()

        statuses = ["PENDING", "SHIPPED", "DELIVERED"]
        for customer in customers:
            for _ in range(random.randint(1, 3)):
                order = Order(
                    customer_id=customer.id,
                    status=random.choice(statuses),
                    total_price=0.0,
                )
                db.add(order)
                db.flush()

                total = 0.0
                selected_products = random.sample(products, k=random.randint(1, min(4, len(products))))
                for product in selected_products:
                    qty = random.randint(1, 3)
                    unit_price = float(product.price)
                    total += unit_price * qty
                    db.add(
                        OrderItem(
                            order_id=order.id,
                            product_id=product.id,
                            quantity=qty,
                            price_at_order=unit_price,
                        )
                    )
                order.total_price = total

        db.commit()
        print("Seed completed with synthetic data.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_data()
