from tools.database import get_db
from tools.models import Order, OrderItem, Customer, Product

def get_orders(customer_name: str = None):
    """Lấy danh sách đơn hàng, có thể lọc theo tên khách hàng"""
    with get_db() as db:
        query = db.query(Order).join(Customer)
        if customer_name:
            query = query.filter(Customer.name.ilike(f"%{customer_name}%"))

        results = query.all()
        return [{
            "order_id": o.id,
            "customer": o.customer.name,
            "status": o.status,
            "total": o.total_price,
            "date": str(o.created_at)
        } for o in results]

def get_order_details(order_id: int):
    """Lấy chi tiết sản phẩm trong một đơn hàng"""
    with get_db() as db:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return {"error": "Không tìm thấy đơn hàng"}

        items = db.query(OrderItem).join(Product).filter(OrderItem.order_id == order_id).all()
        return {
            "order_id": order.id,
            "customer": order.customer.name,
            "status": order.status,
            "items": [{
                "product": i.product.name,
                "quantity": i.quantity,
                "price": i.price_at_order
            } for i in items]
        }
