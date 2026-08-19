import os

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify, session
)
from flask_login import login_required, current_user

from app.extensions import db
from app.decorators import admin_required, super_admin_required, staff_permission
from app.models import (
    Admin, Staff, Customer, Plant, Category, Order, OrderItem, Sale, InventoryLog,
    Supplier, Message, Notification, WebsiteSetting, NavigationItem, Banner,
    HomepageSection, FooterContent, SocialLink, Announcement,
)
from app.utils import (
    slugify, unique_slug, allowed_file, save_uploaded_file, delete_uploaded_file, utcnow
)

bp = Blueprint("admin", __name__, url_prefix="/admin")


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@bp.route("/")
@admin_required
def dashboard():
    total_plants = db.session.execute(db.select(db.func.count(Plant.id))).scalar() or 0
    total_categories = db.session.execute(db.select(db.func.count(Category.id))).scalar() or 0
    total_customers = db.session.execute(db.select(db.func.count(Customer.id))).scalar() or 0
    total_orders = db.session.execute(db.select(db.func.count(Order.id))).scalar() or 0
    pending_orders = db.session.execute(
        db.select(db.func.count(Order.id)).where(Order.status == "Pending")
    ).scalar() or 0
    completed_orders = db.session.execute(
        db.select(db.func.count(Order.id)).where(Order.status == "Completed")
    ).scalar() or 0
    available_stock = db.session.execute(
        db.select(db.func.coalesce(db.func.sum(Plant.stock), 0))
    ).scalar() or 0
    low_stock = (
        db.session.execute(
            db.select(Plant).where(Plant.stock > 0, Plant.stock <= 10).order_by(Plant.stock)
        ).scalars().all()
    )
    total_sales = db.session.execute(
        db.select(db.func.coalesce(db.func.sum(Sale.amount), 0))
        .where(Sale.status.in_(["Completed", "Processing", "Ready", "Confirmed"]))
    ).scalar() or 0

    recent_orders = (
        db.session.execute(db.select(Order).order_by(Order.created_at.desc()).limit(5))
        .scalars().all()
    )
    recent_customers = (
        db.session.execute(db.select(Customer).order_by(Customer.created_at.desc()).limit(5))
        .scalars().all()
    )
    latest_messages = (
        db.session.execute(db.select(Message).order_by(Message.created_at.desc()).limit(5))
        .scalars().all()
    )
    latest_notifications = (
        db.session.execute(
            db.select(Notification).where(Notification.recipient_type == "admin")
            .order_by(Notification.created_at.desc()).limit(5)
        ).scalars().all()
    )
    popular_plants = (
        db.session.execute(
            db.select(Plant).where(Plant.is_available == True, Plant.is_popular == True).limit(6)
        ).scalars().all()
    )

    # Sales by category for chart
    sales_by_category = (
        db.session.execute(
            db.select(Category.name, db.func.coalesce(db.func.sum(Sale.amount), 0))
            .join(Sale, Sale.category_id == Category.id)
            .group_by(Category.name).order_by(db.func.sum(Sale.amount).desc())
        ).all()
    )
    # Monthly sales for chart (computed in Python for DB portability)
    monthly_rows = (
        db.session.execute(
            db.select(Sale.created_at, Sale.amount)
            .where(Sale.status.in_(["Completed", "Processing", "Ready", "Confirmed"]))
        ).all()
    )
    monthly_map = {}
    for created_at, amount in monthly_rows:
        if not created_at:
            continue
        key = created_at.strftime("%Y-%m")
        monthly_map[key] = monthly_map.get(key, 0) + float(amount or 0)
    monthly = sorted(monthly_map.items())

    return render_template(
        "admin/dashboard.html",
        total_plants=total_plants, total_categories=total_categories,
        total_customers=total_customers, total_orders=total_orders,
        pending_orders=pending_orders, completed_orders=completed_orders,
        available_stock=available_stock, low_stock=low_stock,
        total_sales=float(total_sales),
        recent_orders=recent_orders, recent_customers=recent_customers,
        latest_messages=latest_messages, latest_notifications=latest_notifications,
        popular_plants=popular_plants,
        sales_by_category=sales_by_category, monthly=monthly,
    )


# ---------------------------------------------------------------------------
# Plant management
# ---------------------------------------------------------------------------

@bp.route("/plants")
@admin_required
def plants():
    page = request.args.get("page", 1, type=int)
    search = request.args.get("search", "").strip()
    category_id = request.args.get("category", type=int)
    availability = request.args.get("availability", "")
    query = db.select(Plant)
    if search:
        query = query.where(Plant.name.ilike(f"%{search}%"))
    if category_id:
        query = query.where(Plant.category_id == category_id)
    if availability == "available":
        query = query.where(Plant.is_available == True)
    elif availability == "unavailable":
        query = query.where(Plant.is_available == False)
    query = query.order_by(Plant.created_at.desc())
    pagination = db.paginate(query, page=page, per_page=12, error_out=False)
    categories = db.session.execute(db.select(Category).order_by(Category.display_order)).scalars().all()
    return render_template(
        "admin/plants.html", plants=pagination.items, pagination=pagination,
        categories=categories, search=search, category_id=category_id, availability=availability,
    )


@bp.route("/plants/new", methods=["GET", "POST"])
@admin_required
def plant_new():
    categories = db.session.execute(db.select(Category).order_by(Category.display_order)).scalars().all()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category_id = request.form.get("category_id", type=int)
        price = request.form.get("price", type=float)
        stock = request.form.get("stock", 0, type=int)
        if not name or not category_id or price is None:
            flash("Name, category, and price are required.", "error")
        else:
            image = None
            if "image" in request.files and request.files["image"].filename:
                f = request.files["image"]
                if allowed_file(f.filename):
                    image = save_uploaded_file(f, "plants")
                else:
                    flash("Invalid image file type.", "error")
            plant = Plant(
                name=name,
                slug=unique_slug(Plant, name),
                category_id=category_id,
                description=request.form.get("description", ""),
                short_description=request.form.get("short_description", ""),
                price=price,
                stock=stock,
                is_available=bool(request.form.get("is_available")),
                is_featured=bool(request.form.get("is_featured")),
                is_popular=bool(request.form.get("is_popular")),
                plant_type=request.form.get("plant_type", ""),
                size=request.form.get("size", ""),
                care_instructions=request.form.get("care_instructions", ""),
                watering_requirements=request.form.get("watering_requirements", ""),
                sunlight_requirements=request.form.get("sunlight_requirements", ""),
                image=image,
            )
            db.session.add(plant)
            db.session.commit()
            flash("Plant added successfully.", "success")
            return redirect(url_for("admin.plants"))
    return render_template("admin/plant_form.html", plant=None, categories=categories)


@bp.route("/plants/<int:plant_id>/edit", methods=["GET", "POST"])
@admin_required
def plant_edit(plant_id):
    plant = db.session.get(Plant, plant_id)
    if not plant:
        abort(404)
    categories = db.session.execute(db.select(Category).order_by(Category.display_order)).scalars().all()
    if request.method == "POST":
        plant.name = request.form.get("name", "").strip()
        plant.slug = unique_slug(Plant, plant.name, instance_id=plant.id)
        plant.category_id = request.form.get("category_id", type=int)
        plant.price = request.form.get("price", type=float)
        plant.stock = request.form.get("stock", 0, type=int)
        plant.description = request.form.get("description", "")
        plant.short_description = request.form.get("short_description", "")
        plant.is_available = bool(request.form.get("is_available"))
        plant.is_featured = bool(request.form.get("is_featured"))
        plant.is_popular = bool(request.form.get("is_popular"))
        plant.plant_type = request.form.get("plant_type", "")
        plant.size = request.form.get("size", "")
        plant.care_instructions = request.form.get("care_instructions", "")
        plant.watering_requirements = request.form.get("watering_requirements", "")
        plant.sunlight_requirements = request.form.get("sunlight_requirements", "")
        if "image" in request.files and request.files["image"].filename:
            f = request.files["image"]
            if allowed_file(f.filename):
                if plant.image:
                    delete_uploaded_file(plant.image)
                plant.image = save_uploaded_file(f, "plants")
            else:
                flash("Invalid image file type.", "error")
        db.session.commit()
        flash("Plant updated successfully.", "success")
        return redirect(url_for("admin.plants"))
    return render_template("admin/plant_form.html", plant=plant, categories=categories)


@bp.route("/plants/<int:plant_id>/delete", methods=["POST"])
@admin_required
def plant_delete(plant_id):
    plant = db.session.get(Plant, plant_id)
    if not plant:
        abort(404)
    if plant.image:
        delete_uploaded_file(plant.image)
    db.session.delete(plant)
    db.session.commit()
    flash("Plant deleted successfully.", "success")
    return redirect(url_for("admin.plants"))


# ---------------------------------------------------------------------------
# Category management
# ---------------------------------------------------------------------------

@bp.route("/categories")
@admin_required
def categories():
    cats = db.session.execute(db.select(Category).order_by(Category.display_order)).scalars().all()
    return render_template("admin/categories.html", categories=cats)


@bp.route("/categories/new", methods=["GET", "POST"])
@admin_required
def category_new():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Category name is required.", "error")
        elif db.session.execute(db.select(Category).where(Category.name == name)).scalar_one_or_none():
            flash("Category already exists.", "error")
        else:
            image = None
            if "image" in request.files and request.files["image"].filename:
                f = request.files["image"]
                if allowed_file(f.filename):
                    image = save_uploaded_file(f, "categories")
            cat = Category(
                name=name, slug=unique_slug(Plant, name),
                description=request.form.get("description", ""),
                image=image,
                is_active=bool(request.form.get("is_active")),
                display_order=request.form.get("display_order", 0, type=int),
            )
            db.session.add(cat)
            db.session.commit()
            flash("Category added successfully.", "success")
            return redirect(url_for("admin.categories"))
    return render_template("admin/category_form.html", category=None)


@bp.route("/categories/<int:category_id>/edit", methods=["GET", "POST"])
@admin_required
def category_edit(category_id):
    cat = db.session.get(Category, category_id)
    if not cat:
        abort(404)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        cat.name = name
        cat.slug = slugify(name) or name.lower().replace(" ", "-")
        cat.description = request.form.get("description", "")
        cat.is_active = bool(request.form.get("is_active"))
        cat.display_order = request.form.get("display_order", 0, type=int)
        if "image" in request.files and request.files["image"].filename:
            f = request.files["image"]
            if allowed_file(f.filename):
                if cat.image:
                    delete_uploaded_file(cat.image)
                cat.image = save_uploaded_file(f, "categories")
        db.session.commit()
        flash("Category updated successfully.", "success")
        return redirect(url_for("admin.categories"))
    return render_template("admin/category_form.html", category=cat)


@bp.route("/categories/<int:category_id>/delete", methods=["POST"])
@admin_required
def category_delete(category_id):
    cat = db.session.get(Category, category_id)
    if not cat:
        abort(404)
    if db.session.execute(db.select(db.func.count(Plant.id)).where(Plant.category_id == cat.id)).scalar():
        flash("Cannot delete category with existing plants. Reassign plants first.", "error")
        return redirect(url_for("admin.categories"))
    if cat.image:
        delete_uploaded_file(cat.image)
    db.session.delete(cat)
    db.session.commit()
    flash("Category deleted successfully.", "success")
    return redirect(url_for("admin.categories"))


# ---------------------------------------------------------------------------
# Inventory management
# ---------------------------------------------------------------------------

@bp.route("/inventory")
@admin_required
def inventory():
    page = request.args.get("page", 1, type=int)
    query = db.select(Plant).order_by(Plant.stock.asc())
    pagination = db.paginate(query, page=page, per_page=20, error_out=False)
    return render_template("admin/inventory.html", plants=pagination.items, pagination=pagination)


@bp.route("/inventory/<int:plant_id>/adjust", methods=["POST"])
@admin_required
def inventory_adjust(plant_id):
    plant = db.session.get(Plant, plant_id)
    if not plant:
        abort(404)
    change = request.form.get("change", 0, type=int)
    reason = request.form.get("reason", "Manual adjustment")
    previous = plant.stock
    plant.stock = max(0, plant.stock + change)
    if plant.stock <= 0:
        plant.is_available = False
    elif change > 0 and not plant.is_available:
        plant.is_available = True
    db.session.add(InventoryLog(
        plant_id=plant.id, change=change, previous_stock=previous,
        new_stock=plant.stock, reason=reason,
    ))
    db.session.commit()
    flash("Inventory updated successfully.", "success")
    return redirect(url_for("admin.inventory"))


# ---------------------------------------------------------------------------
# Customer management
# ---------------------------------------------------------------------------

@bp.route("/customers")
@admin_required
def customers():
    page = request.args.get("page", 1, type=int)
    search = request.args.get("search", "").strip()
    query = db.select(Customer)
    if search:
        query = query.where(
            (Customer.username.ilike(f"%{search}%")) | (Customer.email.ilike(f"%{search}%"))
            | (Customer.full_name.ilike(f"%{search}%"))
        )
    query = query.order_by(Customer.created_at.desc())
    pagination = db.paginate(query, page=page, per_page=15, error_out=False)
    return render_template("admin/customers.html", customers=pagination.items, pagination=pagination, search=search)


@bp.route("/customers/<int:customer_id>")
@admin_required
def customer_detail(customer_id):
    customer = db.session.get(Customer, customer_id)
    if not customer:
        abort(404)
    orders = db.session.execute(
        db.select(Order).where(Order.customer_id == customer.id).order_by(Order.created_at.desc())
    ).scalars().all()
    return render_template("admin/customer_detail.html", customer=customer, orders=orders)


@bp.route("/customers/<int:customer_id>/toggle", methods=["POST"])
@admin_required
def customer_toggle(customer_id):
    customer = db.session.get(Customer, customer_id)
    if not customer:
        abort(404)
    customer.is_active = not customer.is_active
    db.session.commit()
    flash("Customer status updated.", "success")
    return redirect(url_for("admin.customers"))


# ---------------------------------------------------------------------------
# Order management
# ---------------------------------------------------------------------------

@bp.route("/orders")
@admin_required
def orders():
    page = request.args.get("page", 1, type=int)
    status = request.args.get("status", "")
    search = request.args.get("search", "").strip()
    query = db.select(Order)
    if status:
        query = query.where(Order.status == status)
    if search:
        query = query.join(Customer).where(
            (Customer.username.ilike(f"%{search}%")) | (Customer.email.ilike(f"%{search}%"))
            | (Customer.full_name.ilike(f"%{search}%")) | (Order.order_number.ilike(f"%{search}%"))
        )
    query = query.order_by(Order.created_at.desc())
    pagination = db.paginate(query, page=page, per_page=15, error_out=False)
    return render_template(
        "admin/orders.html", orders=pagination.items, pagination=pagination,
        status=status, search=search,
    )


@bp.route("/orders/<int:order_id>")
@admin_required
def order_detail(order_id):
    order = db.session.get(Order, order_id)
    if not order:
        abort(404)
    return render_template("admin/order_detail.html", order=order)


@bp.route("/orders/<int:order_id>/status", methods=["POST"])
@admin_required
def order_status(order_id):
    order = db.session.get(Order, order_id)
    if not order:
        abort(404)
    new_status = request.form.get("status", "")
    if new_status in ["Pending", "Confirmed", "Processing", "Ready", "Completed", "Cancelled"]:
        old = order.status
        order.status = new_status
        # Update sale statuses
        for sale in order.sales:
            sale.status = new_status
        db.session.commit()
        # Notify customer
        db.session.add(Notification(
            recipient_type="customer", recipient_id=order.customer_id,
            title="Order Status Updated",
            message=f"Your order {order.order_number} status changed from {old} to {new_status}.",
            link=url_for("customer.order_detail", order_id=order.id), notification_type="order",
        ))
        db.session.commit()
        flash("Order status updated and customer notified.", "success")
    return redirect(url_for("admin.order_detail", order_id=order.id))


# ---------------------------------------------------------------------------
# Sales
# ---------------------------------------------------------------------------

@bp.route("/sales")
@admin_required
def sales():
    total_sales = db.session.execute(
        db.select(db.func.coalesce(db.func.sum(Sale.amount), 0))
        .where(Sale.status.in_(["Completed", "Processing", "Ready", "Confirmed"]))
    ).scalar() or 0
    total_orders = db.session.execute(db.select(db.func.count(db.distinct(Sale.order_id)))).scalar() or 0
    completed = db.session.execute(
        db.select(db.func.coalesce(db.func.sum(Sale.amount), 0)).where(Sale.status == "Completed")
    ).scalar() or 0
    pending = db.session.execute(
        db.select(db.func.coalesce(db.func.sum(Sale.amount), 0)).where(Sale.status == "Pending")
    ).scalar() or 0
    cancelled = db.session.execute(
        db.select(db.func.coalesce(db.func.sum(Sale.amount), 0)).where(Sale.status == "Cancelled")
    ).scalar() or 0

    by_plant = (
        db.session.execute(
            db.select(Sale.plant_name, db.func.coalesce(db.func.sum(Sale.amount), 0), db.func.coalesce(db.func.sum(Sale.quantity), 0))
            .group_by(Sale.plant_name).order_by(db.func.sum(Sale.amount).desc()).limit(10)
        ).all()
    )
    by_category = (
        db.session.execute(
            db.select(Category.name, db.func.coalesce(db.func.sum(Sale.amount), 0))
            .join(Sale, Sale.category_id == Category.id)
            .group_by(Category.name).order_by(db.func.sum(Sale.amount).desc())
        ).all()
    )
    recent = (
        db.session.execute(db.select(Sale).order_by(Sale.created_at.desc()).limit(15))
        .scalars().all()
    )
    return render_template(
        "admin/sales.html",
        total_sales=float(total_sales), total_orders=total_orders,
        completed=float(completed), pending=float(pending), cancelled=float(cancelled),
        by_plant=by_plant, by_category=by_category, recent=recent,
    )


# ---------------------------------------------------------------------------
# Suppliers
# ---------------------------------------------------------------------------

@bp.route("/suppliers")
@admin_required
def suppliers():
    sups = db.session.execute(db.select(Supplier).order_by(Supplier.name)).scalars().all()
    return render_template("admin/suppliers.html", suppliers=sups)


@bp.route("/suppliers/new", methods=["GET", "POST"])
@admin_required
def supplier_new():
    if request.method == "POST":
        sup = Supplier(
            name=request.form.get("name", "").strip(),
            contact_person=request.form.get("contact_person", ""),
            phone=request.form.get("phone", ""),
            email=request.form.get("email", ""),
            address=request.form.get("address", ""),
            supplied_products=request.form.get("supplied_products", ""),
            notes=request.form.get("notes", ""),
            is_active=bool(request.form.get("is_active")),
        )
        db.session.add(sup)
        db.session.commit()
        flash("Supplier added successfully.", "success")
        return redirect(url_for("admin.suppliers"))
    return render_template("admin/supplier_form.html", supplier=None)


@bp.route("/suppliers/<int:supplier_id>/edit", methods=["GET", "POST"])
@admin_required
def supplier_edit(supplier_id):
    sup = db.session.get(Supplier, supplier_id)
    if not sup:
        abort(404)
    if request.method == "POST":
        sup.name = request.form.get("name", "").strip()
        sup.contact_person = request.form.get("contact_person", "")
        sup.phone = request.form.get("phone", "")
        sup.email = request.form.get("email", "")
        sup.address = request.form.get("address", "")
        sup.supplied_products = request.form.get("supplied_products", "")
        sup.notes = request.form.get("notes", "")
        sup.is_active = bool(request.form.get("is_active"))
        db.session.commit()
        flash("Supplier updated successfully.", "success")
        return redirect(url_for("admin.suppliers"))
    return render_template("admin/supplier_form.html", supplier=sup)


@bp.route("/suppliers/<int:supplier_id>/delete", methods=["POST"])
@admin_required
def supplier_delete(supplier_id):
    sup = db.session.get(Supplier, supplier_id)
    if not sup:
        abort(404)
    db.session.delete(sup)
    db.session.commit()
    flash("Supplier deleted successfully.", "success")
    return redirect(url_for("admin.suppliers"))


# ---------------------------------------------------------------------------
# Staff management
# ---------------------------------------------------------------------------

@bp.route("/staff")
@super_admin_required
def staff():
    staff_list = db.session.execute(db.select(Staff).order_by(Staff.created_at.desc())).scalars().all()
    return render_template("admin/staff.html", staff_list=staff_list)


@bp.route("/staff/new", methods=["GET", "POST"])
@super_admin_required
def staff_new():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        if not username or not email or len(password) < 6:
            flash("Username, email, and password (min 6 chars) are required.", "error")
        elif db.session.execute(db.select(Staff).where((Staff.username == username) | (Staff.email == email))).scalar_one_or_none():
            flash("Username or email already exists.", "error")
        else:
            s = Staff(
                username=username, email=email,
                full_name=request.form.get("full_name", ""),
                phone=request.form.get("phone", ""),
                role=request.form.get("role", "Staff"),
                permissions=request.form.get("permissions", ""),
                is_active=bool(request.form.get("is_active")),
            )
            s.set_password(password)
            db.session.add(s)
            db.session.commit()
            flash("Staff added successfully.", "success")
            return redirect(url_for("admin.staff"))
    return render_template("admin/staff_form.html", staff_member=None)


@bp.route("/staff/<int:staff_id>/edit", methods=["GET", "POST"])
@super_admin_required
def staff_edit(staff_id):
    s = db.session.get(Staff, staff_id)
    if not s:
        abort(404)
    if request.method == "POST":
        s.username = request.form.get("username", "").strip()
        s.email = request.form.get("email", "").strip()
        s.full_name = request.form.get("full_name", "")
        s.phone = request.form.get("phone", "")
        s.role = request.form.get("role", "Staff")
        s.permissions = request.form.get("permissions", "")
        s.is_active = bool(request.form.get("is_active"))
        pw = request.form.get("password", "")
        if pw:
            s.set_password(pw)
        db.session.commit()
        flash("Staff updated successfully.", "success")
        return redirect(url_for("admin.staff"))
    return render_template("admin/staff_form.html", staff_member=s)


@bp.route("/staff/<int:staff_id>/delete", methods=["POST"])
@super_admin_required
def staff_delete(staff_id):
    s = db.session.get(Staff, staff_id)
    if not s:
        abort(404)
    db.session.delete(s)
    db.session.commit()
    flash("Staff deleted successfully.", "success")
    return redirect(url_for("admin.staff"))


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

@bp.route("/messages")
@admin_required
def messages():
    page = request.args.get("page", 1, type=int)
    filter_unread = request.args.get("unread", "")
    query = db.select(Message)
    if filter_unread == "1":
        query = query.where(Message.is_read == False)
    query = query.order_by(Message.created_at.desc())
    pagination = db.paginate(query, page=page, per_page=15, error_out=False)
    unread_count = db.session.execute(
        db.select(db.func.count(Message.id)).where(Message.is_read == False)
    ).scalar() or 0
    return render_template(
        "admin/messages.html", messages=pagination.items, pagination=pagination,
        unread_count=unread_count, filter_unread=filter_unread,
    )


@bp.route("/messages/<int:message_id>", methods=["GET", "POST"])
@admin_required
def message_detail(message_id):
    msg = db.session.get(Message, message_id)
    if not msg:
        abort(404)
    if request.method == "POST":
        reply = request.form.get("reply", "").strip()
        if reply:
            msg.admin_reply = reply
            msg.replied_at = utcnow()
            msg.is_read = True
            db.session.commit()
            if msg.customer_id:
                db.session.add(Notification(
                    recipient_type="customer", recipient_id=msg.customer_id,
                    title="Message Reply", message=f"Admin replied to your message: {reply[:100]}",
                    link=url_for("main.contact"), notification_type="message",
                ))
                db.session.commit()
            flash("Reply sent.", "success")
        return redirect(url_for("admin.messages"))
    if not msg.is_read:
        msg.is_read = True
        db.session.commit()
    return render_template("admin/message_detail.html", message=msg)


@bp.route("/messages/<int:message_id>/delete", methods=["POST"])
@admin_required
def message_delete(message_id):
    msg = db.session.get(Message, message_id)
    if not msg:
        abort(404)
    db.session.delete(msg)
    db.session.commit()
    flash("Message deleted.", "success")
    return redirect(url_for("admin.messages"))


# ---------------------------------------------------------------------------
# Notifications (admin)
# ---------------------------------------------------------------------------

@bp.route("/notifications")
@admin_required
def notifications():
    notes = db.session.execute(
        db.select(Notification).where(Notification.recipient_type == "admin")
        .order_by(Notification.created_at.desc())
    ).scalars().all()
    return render_template("admin/notifications.html", notifications=notes)


@bp.route("/notifications/new", methods=["GET", "POST"])
@admin_required
def notification_new():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        message = request.form.get("message", "").strip()
        target = request.form.get("target", "all")  # all, customers, admins
        link = request.form.get("link", "")
        if not title:
            flash("Title is required.", "error")
        else:
            if target == "customers":
                customers = db.session.execute(db.select(Customer).where(Customer.is_active == True)).scalars().all()
                for c in customers:
                    db.session.add(Notification(
                        recipient_type="customer", recipient_id=c.id, title=title,
                        message=message, link=link, notification_type="announcement",
                    ))
            elif target == "admins":
                db.session.add(Notification(
                    recipient_type="admin", title=title, message=message, link=link,
                    notification_type="announcement",
                ))
            else:
                # all customers + admins
                customers = db.session.execute(db.select(Customer).where(Customer.is_active == True)).scalars().all()
                for c in customers:
                    db.session.add(Notification(
                        recipient_type="customer", recipient_id=c.id, title=title,
                        message=message, link=link, notification_type="announcement",
                    ))
                db.session.add(Notification(
                    recipient_type="admin", title=title, message=message, link=link,
                    notification_type="announcement",
                ))
            db.session.commit()
            flash("Notification sent.", "success")
            return redirect(url_for("admin.notifications"))
    return render_template("admin/notification_form.html")


@bp.route("/notifications/<int:notification_id>/delete", methods=["POST"])
@admin_required
def notification_delete(notification_id):
    note = db.session.get(Notification, notification_id)
    if note:
        db.session.delete(note)
        db.session.commit()
        flash("Notification deleted.", "success")
    return redirect(url_for("admin.notifications"))


# ---------------------------------------------------------------------------
# Website management
# ---------------------------------------------------------------------------

@bp.route("/website", methods=["GET", "POST"])
@admin_required
def website_management():
    if request.method == "POST":
        for key in ["site_name", "tagline", "about_short", "about_full",
                    "contact_address", "contact_phone", "contact_email",
                    "footer_about", "copyright", "meta_description"]:
            if key in request.form:
                WebsiteSetting.set_value(key, request.form.get(key, ""))
        # Logo
        if "logo" in request.files and request.files["logo"].filename:
            f = request.files["logo"]
            if allowed_file(f.filename, {"png", "jpg", "jpeg", "gif", "webp", "svg", "ico"}):
                old = WebsiteSetting.get_value("logo")
                if old:
                    delete_uploaded_file(old)
                WebsiteSetting.set_value("logo", save_uploaded_file(f, "branding"))
            else:
                flash("Invalid logo file type.", "error")
        # Favicon
        if "favicon" in request.files and request.files["favicon"].filename:
            f = request.files["favicon"]
            if allowed_file(f.filename, {"png", "jpg", "jpeg", "gif", "ico", "svg", "webp"}):
                old = WebsiteSetting.get_value("favicon")
                if old:
                    delete_uploaded_file(old)
                WebsiteSetting.set_value("favicon", save_uploaded_file(f, "branding"))
            else:
                flash("Invalid favicon file type.", "error")
        db.session.commit()
        flash("Website settings updated.", "success")
        return redirect(url_for("admin.website_management"))

    settings = {s.key: s.value for s in db.session.execute(db.select(WebsiteSetting)).scalars().all()}
    return render_template("admin/website_management.html", settings=settings)


# ---------------------------------------------------------------------------
# Navigation management
# ---------------------------------------------------------------------------

@bp.route("/navigation")
@admin_required
def navigation():
    items = db.session.execute(
        db.select(NavigationItem).order_by(NavigationItem.location, NavigationItem.display_order)
    ).scalars().all()
    return render_template("admin/navigation.html", items=items)


@bp.route("/navigation/new", methods=["GET", "POST"])
@admin_required
def navigation_new():
    if request.method == "POST":
        item = NavigationItem(
            label=request.form.get("label", "").strip(),
            url=request.form.get("url", "").strip(),
            display_order=request.form.get("display_order", 0, type=int),
            is_active=bool(request.form.get("is_active")),
            location=request.form.get("location", "main"),
        )
        db.session.add(item)
        db.session.commit()
        flash("Navigation item added.", "success")
        return redirect(url_for("admin.navigation"))
    return render_template("admin/navigation_form.html", item=None)


@bp.route("/navigation/<int:item_id>/edit", methods=["GET", "POST"])
@admin_required
def navigation_edit(item_id):
    item = db.session.get(NavigationItem, item_id)
    if not item:
        abort(404)
    if request.method == "POST":
        item.label = request.form.get("label", "").strip()
        item.url = request.form.get("url", "").strip()
        item.display_order = request.form.get("display_order", 0, type=int)
        item.is_active = bool(request.form.get("is_active"))
        item.location = request.form.get("location", "main")
        db.session.commit()
        flash("Navigation item updated.", "success")
        return redirect(url_for("admin.navigation"))
    return render_template("admin/navigation_form.html", item=item)


@bp.route("/navigation/<int:item_id>/delete", methods=["POST"])
@admin_required
def navigation_delete(item_id):
    item = db.session.get(NavigationItem, item_id)
    if item:
        db.session.delete(item)
        db.session.commit()
        flash("Navigation item deleted.", "success")
    return redirect(url_for("admin.navigation"))


# ---------------------------------------------------------------------------
# Banners
# ---------------------------------------------------------------------------

@bp.route("/banners")
@admin_required
def banners():
    items = db.session.execute(db.select(Banner).order_by(Banner.display_order)).scalars().all()
    return render_template("admin/banners.html", banners=items)


@bp.route("/banners/new", methods=["GET", "POST"])
@admin_required
def banner_new():
    if request.method == "POST":
        image = None
        if "image" in request.files and request.files["image"].filename:
            f = request.files["image"]
            if allowed_file(f.filename):
                image = save_uploaded_file(f, "banners")
            else:
                flash("Invalid image file type.", "error")
        b = Banner(
            title=request.form.get("title", ""),
            description=request.form.get("description", ""),
            image=image,
            cta_text=request.form.get("cta_text", ""),
            cta_link=request.form.get("cta_link", ""),
            is_active=bool(request.form.get("is_active")),
            display_order=request.form.get("display_order", 0, type=int),
        )
        db.session.add(b)
        db.session.commit()
        flash("Banner added.", "success")
        return redirect(url_for("admin.banners"))
    return render_template("admin/banner_form.html", banner=None)


@bp.route("/banners/<int:banner_id>/edit", methods=["GET", "POST"])
@admin_required
def banner_edit(banner_id):
    b = db.session.get(Banner, banner_id)
    if not b:
        abort(404)
    if request.method == "POST":
        b.title = request.form.get("title", "")
        b.description = request.form.get("description", "")
        b.cta_text = request.form.get("cta_text", "")
        b.cta_link = request.form.get("cta_link", "")
        b.is_active = bool(request.form.get("is_active"))
        b.display_order = request.form.get("display_order", 0, type=int)
        if "image" in request.files and request.files["image"].filename:
            f = request.files["image"]
            if allowed_file(f.filename):
                if b.image:
                    delete_uploaded_file(b.image)
                b.image = save_uploaded_file(f, "banners")
        db.session.commit()
        flash("Banner updated.", "success")
        return redirect(url_for("admin.banners"))
    return render_template("admin/banner_form.html", banner=b)


@bp.route("/banners/<int:banner_id>/delete", methods=["POST"])
@admin_required
def banner_delete(banner_id):
    b = db.session.get(Banner, banner_id)
    if b:
        if b.image:
            delete_uploaded_file(b.image)
        db.session.delete(b)
        db.session.commit()
        flash("Banner deleted.", "success")
    return redirect(url_for("admin.banners"))


# ---------------------------------------------------------------------------
# Homepage sections
# ---------------------------------------------------------------------------

@bp.route("/homepage")
@admin_required
def homepage_management():
    sections = db.session.execute(
        db.select(HomepageSection).order_by(HomepageSection.display_order)
    ).scalars().all()
    return render_template("admin/homepage_sections.html", sections=sections)


@bp.route("/homepage/new", methods=["GET", "POST"])
@admin_required
def homepage_section_new():
    if request.method == "POST":
        image = None
        if "image" in request.files and request.files["image"].filename:
            f = request.files["image"]
            if allowed_file(f.filename):
                image = save_uploaded_file(f, "sections")
        s = HomepageSection(
            section_type=request.form.get("section_type", "custom"),
            title=request.form.get("title", ""),
            description=request.form.get("description", ""),
            image=image,
            button_text=request.form.get("button_text", ""),
            button_link=request.form.get("button_link", ""),
            is_active=bool(request.form.get("is_active")),
            display_order=request.form.get("display_order", 0, type=int),
        )
        db.session.add(s)
        db.session.commit()
        flash("Section added.", "success")
        return redirect(url_for("admin.homepage_management"))
    return render_template("admin/homepage_section_form.html", section=None)


@bp.route("/homepage/<int:section_id>/edit", methods=["GET", "POST"])
@admin_required
def homepage_section_edit(section_id):
    s = db.session.get(HomepageSection, section_id)
    if not s:
        abort(404)
    if request.method == "POST":
        s.section_type = request.form.get("section_type", "custom")
        s.title = request.form.get("title", "")
        s.description = request.form.get("description", "")
        s.button_text = request.form.get("button_text", "")
        s.button_link = request.form.get("button_link", "")
        s.is_active = bool(request.form.get("is_active"))
        s.display_order = request.form.get("display_order", 0, type=int)
        if "image" in request.files and request.files["image"].filename:
            f = request.files["image"]
            if allowed_file(f.filename):
                if s.image:
                    delete_uploaded_file(s.image)
                s.image = save_uploaded_file(f, "sections")
        db.session.commit()
        flash("Section updated.", "success")
        return redirect(url_for("admin.homepage_management"))
    return render_template("admin/homepage_section_form.html", section=s)


@bp.route("/homepage/<int:section_id>/delete", methods=["POST"])
@admin_required
def homepage_section_delete(section_id):
    s = db.session.get(HomepageSection, section_id)
    if s:
        if s.image:
            delete_uploaded_file(s.image)
        db.session.delete(s)
        db.session.commit()
        flash("Section deleted.", "success")
    return redirect(url_for("admin.homepage_management"))


# ---------------------------------------------------------------------------
# Footer management
# ---------------------------------------------------------------------------

@bp.route("/footer", methods=["GET", "POST"])
@admin_required
def footer_management():
    footer = db.session.execute(db.select(FooterContent)).scalars().first()
    if request.method == "POST":
        if not footer:
            footer = FooterContent()
            db.session.add(footer)
        footer.about_text = request.form.get("about_text", "")
        footer.copyright_text = request.form.get("copyright_text", "")
        footer.contact_address = request.form.get("contact_address", "")
        footer.contact_phone = request.form.get("contact_phone", "")
        footer.contact_email = request.form.get("contact_email", "")
        footer.show_categories = bool(request.form.get("show_categories"))
        footer.show_quick_links = bool(request.form.get("show_quick_links"))
        db.session.commit()
        flash("Footer updated.", "success")
        return redirect(url_for("admin.footer_management"))
    return render_template("admin/footer_management.html", footer=footer)


# ---------------------------------------------------------------------------
# Social links
# ---------------------------------------------------------------------------

@bp.route("/social")
@admin_required
def social_links():
    links = db.session.execute(db.select(SocialLink).order_by(SocialLink.display_order)).scalars().all()
    return render_template("admin/social_links.html", links=links)


@bp.route("/social/new", methods=["GET", "POST"])
@admin_required
def social_new():
    if request.method == "POST":
        link = SocialLink(
            platform=request.form.get("platform", "").strip(),
            url=request.form.get("url", "").strip(),
            is_active=bool(request.form.get("is_active")),
            display_order=request.form.get("display_order", 0, type=int),
        )
        db.session.add(link)
        db.session.commit()
        flash("Social link added.", "success")
        return redirect(url_for("admin.social_links"))
    return render_template("admin/social_form.html", link=None)


@bp.route("/social/<int:link_id>/edit", methods=["GET", "POST"])
@admin_required
def social_edit(link_id):
    link = db.session.get(SocialLink, link_id)
    if not link:
        abort(404)
    if request.method == "POST":
        link.platform = request.form.get("platform", "").strip()
        link.url = request.form.get("url", "").strip()
        link.is_active = bool(request.form.get("is_active"))
        link.display_order = request.form.get("display_order", 0, type=int)
        db.session.commit()
        flash("Social link updated.", "success")
        return redirect(url_for("admin.social_links"))
    return render_template("admin/social_form.html", link=link)


@bp.route("/social/<int:link_id>/delete", methods=["POST"])
@admin_required
def social_delete(link_id):
    link = db.session.get(SocialLink, link_id)
    if link:
        db.session.delete(link)
        db.session.commit()
        flash("Social link deleted.", "success")
    return redirect(url_for("admin.social_links"))


# ---------------------------------------------------------------------------
# Announcements
# ---------------------------------------------------------------------------

@bp.route("/announcements")
@admin_required
def announcements():
    items = db.session.execute(db.select(Announcement).order_by(Announcement.display_order)).scalars().all()
    return render_template("admin/announcements.html", announcements=items)


@bp.route("/announcements/new", methods=["GET", "POST"])
@admin_required
def announcement_new():
    if request.method == "POST":
        a = Announcement(
            title=request.form.get("title", "").strip(),
            message=request.form.get("message", ""),
            is_active=bool(request.form.get("is_active")),
            display_order=request.form.get("display_order", 0, type=int),
        )
        db.session.add(a)
        db.session.commit()
        flash("Announcement added.", "success")
        return redirect(url_for("admin.announcements"))
    return render_template("admin/announcement_form.html", announcement=None)


@bp.route("/announcements/<int:announcement_id>/edit", methods=["GET", "POST"])
@admin_required
def announcement_edit(announcement_id):
    a = db.session.get(Announcement, announcement_id)
    if not a:
        abort(404)
    if request.method == "POST":
        a.title = request.form.get("title", "").strip()
        a.message = request.form.get("message", "")
        a.is_active = bool(request.form.get("is_active"))
        a.display_order = request.form.get("display_order", 0, type=int)
        db.session.commit()
        flash("Announcement updated.", "success")
        return redirect(url_for("admin.announcements"))
    return render_template("admin/announcement_form.html", announcement=a)


@bp.route("/announcements/<int:announcement_id>/delete", methods=["POST"])
@admin_required
def announcement_delete(announcement_id):
    a = db.session.get(Announcement, announcement_id)
    if a:
        db.session.delete(a)
        db.session.commit()
        flash("Announcement deleted.", "success")
    return redirect(url_for("admin.announcements"))


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

@bp.route("/reports")
@admin_required
def reports():
    return render_template("admin/reports.html")


@bp.route("/reports/plants")
@admin_required
def report_plants():
    plants = db.session.execute(db.select(Plant).order_by(Plant.name)).scalars().all()
    return render_template("admin/reports/plants.html", plants=plants)


@bp.route("/reports/inventory")
@admin_required
def report_inventory():
    plants = db.session.execute(db.select(Plant).order_by(Plant.stock)).scalars().all()
    return render_template("admin/reports/inventory.html", plants=plants)


@bp.route("/reports/customers")
@admin_required
def report_customers():
    customers = db.session.execute(db.select(Customer).order_by(Customer.created_at.desc())).scalars().all()
    return render_template("admin/reports/customers.html", customers=customers)


@bp.route("/reports/orders")
@admin_required
def report_orders():
    orders = db.session.execute(db.select(Order).order_by(Order.created_at.desc())).scalars().all()
    return render_template("admin/reports/orders.html", orders=orders)


@bp.route("/reports/sales")
@admin_required
def report_sales():
    sales = db.session.execute(db.select(Sale).order_by(Sale.created_at.desc())).scalars().all()
    return render_template("admin/reports/sales.html", sales=sales)


@bp.route("/reports/categories")
@admin_required
def report_categories():
    cats = db.session.execute(db.select(Category).order_by(Category.name)).scalars().all()
    return render_template("admin/reports/categories.html", categories=cats)


# ---------------------------------------------------------------------------
# Settings / admin account
# ---------------------------------------------------------------------------

@bp.route("/settings", methods=["GET", "POST"])
@admin_required
def settings():
    if request.method == "POST":
        action = request.form.get("action", "")
        if action == "profile":
            current_user.full_name = request.form.get("full_name", "")
            current_user.email = request.form.get("email", "")
            current_user.phone = request.form.get("phone", "")
            db.session.commit()
            flash("Account updated.", "success")
        elif action == "password":
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
        return redirect(url_for("admin.settings"))
    return render_template("admin/settings.html")
