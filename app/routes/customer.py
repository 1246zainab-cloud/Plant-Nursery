import secrets

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, session, abort
)
from flask_login import login_required, current_user

from app.extensions import db
from app.decorators import customer_required
from app.models import (
    Order, OrderItem, Plant, Notification, Customer, Sale, InventoryLog
)
from app.utils import utcnow

bp = Blueprint("customer", __name__, url_prefix="/customer")


@bp.route("/profile")
@customer_required
def profile():
    orders = (
        db.session.execute(
            db.select(Order)
            .where(Order.customer_id == current_user.id)
            .order_by(Order.created_at.desc())
            .limit(5)
        ).scalars().all()
    )
    return render_template("customer/profile.html", orders=orders)


@bp.route("/orders")
@customer_required
def orders():
    page = request.args.get("page", 1, type=int)
    query = db.select(Order).where(Order.customer_id == current_user.id).order_by(Order.created_at.desc())
    pagination = db.paginate(query, page=page, per_page=10, error_out=False)
    return render_template("customer/orders.html", orders=pagination.items, pagination=pagination)


@bp.route("/orders/<int:order_id>")
@customer_required
def order_detail(order_id):
    order = db.session.get(Order, order_id)
    if not order or order.customer_id != current_user.id:
        abort(404)
    return render_template("customer/order_detail.html", order=order)


@bp.route("/profile/edit", methods=["GET", "POST"])
@customer_required
def edit_profile():
    if request.method == "POST":
        current_user.full_name = request.form.get("full_name", "").strip()
        current_user.phone = request.form.get("phone", "").strip()
        current_user.address = request.form.get("address", "").strip()
        current_user.city = request.form.get("city", "").strip()
        current_user.state = request.form.get("state", "").strip()
        current_user.zip_code = request.form.get("zip_code", "").strip()
        current_user.country = request.form.get("country", "").strip()
        db.session.commit()
        flash("Profile updated successfully.", "success")
        return redirect(url_for("customer.profile"))
    return render_template("customer/edit_profile.html")


@bp.route("/profile/change-password", methods=["GET", "POST"])
@customer_required
def change_password():
    if request.method == "POST":
        current = request.form.get("current_password", "")
        new = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")
        if not current_user.check_password(current):
            flash("Current password is incorrect.", "error")
        elif len(new) < 6:
            flash("New password must be at least 6 characters.", "error")
        elif new != confirm:
            flash("New passwords do not match.", "error")
        else:
            current_user.set_password(new)
            db.session.commit()
            flash("Password changed successfully.", "success")
            return redirect(url_for("customer.profile"))
    return render_template("customer/change_password.html")


@bp.route("/checkout", methods=["GET", "POST"])
@customer_required
def checkout():
    cart = session.get("cart", {})
    if not cart:
        flash("Your cart is empty.", "info")
        return redirect(url_for("main.cart"))

    items = []
    total = 0.0
    for pid, data in list(cart.items()):
        plant = db.session.get(Plant, int(pid))
        if not plant or not plant.is_available:
            cart.pop(pid, None)
            continue
        qty = data.get("quantity", 1)
        if qty > plant.stock:
            qty = plant.stock
            cart[pid] = {"quantity": qty}
        line_total = float(plant.price) * qty
        total += line_total
        items.append({"plant": plant, "quantity": qty, "line_total": line_total})
    session["cart"] = cart

    if request.method == "POST":
        # Validate stock again
        for it in items:
            plant = it["plant"]
            if it["quantity"] > plant.stock:
                flash(f"Not enough stock for {plant.name}.", "error")
                return redirect(url_for("main.cart"))

        order = Order(
            order_number=_generate_order_number(),
            customer_id=current_user.id,
            status="Pending",
            subtotal=total,
            total=total,
            shipping_address=request.form.get("shipping_address", current_user.address) or "",
            contact_phone=request.form.get("contact_phone", current_user.phone) or "",
            notes=request.form.get("notes", "") or "",
            payment_method=request.form.get("payment_method", "Cash on Delivery") or "Cash on Delivery",
        )
        db.session.add(order)
        db.session.flush()

        for it in items:
            plant = it["plant"]
            oi = OrderItem(
                order_id=order.id,
                plant_id=plant.id,
                plant_name=plant.name,
                quantity=it["quantity"],
                unit_price=plant.price,
            )
            db.session.add(oi)
            db.session.flush()  # ensure oi.id is generated before referencing it
            # Deduct inventory
            previous = plant.stock
            plant.stock -= it["quantity"]
            if plant.stock <= 0:
                plant.is_available = False
            db.session.add(InventoryLog(
                plant_id=plant.id, change=-it["quantity"],
                previous_stock=previous, new_stock=plant.stock,
                reason="Order placed", reference=order.order_number,
            ))
            # Sale record
            db.session.add(Sale(
                order_id=order.id, order_item_id=oi.id, customer_id=current_user.id,
                plant_id=plant.id, category_id=plant.category_id,
                plant_name=plant.name,
                customer_name=current_user.full_name or current_user.username,
                order_number=order.order_number,
                unit_price=plant.price,
                quantity=it["quantity"], amount=float(plant.price) * it["quantity"],
                status="Pending",
            ))

        db.session.commit()

        # Notify customer
        db.session.add(Notification(
            recipient_type="customer", recipient_id=current_user.id,
            title="Order Placed", message=f"Your order {order.order_number} has been placed successfully.",
            link=url_for("customer.order_detail", order_id=order.id), notification_type="order",
        ))
        # Notify admin
        db.session.add(Notification(
            recipient_type="admin", title="New Order",
            message=f"New order {order.order_number} from {current_user.full_name or current_user.username}.",
            link=url_for("admin.order_detail", order_id=order.id), notification_type="order",
        ))
        db.session.commit()

        session.pop("cart", None)
        flash("Your order has been placed successfully!", "success")
        return redirect(url_for("customer.order_detail", order_id=order.id))

    return render_template("customer/checkout.html", items=items, total=total)


def _generate_order_number():
    return "ORD-" + utcnow().strftime("%Y%m%d") + "-" + secrets.token_hex(4).upper()
