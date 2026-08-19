from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, session, abort, jsonify
)
from flask_login import current_user

from app.extensions import db
from app.models import (
    Plant, Category, Banner, HomepageSection, Announcement, Message, Notification
)
from app.utils import slugify, allowed_file, save_uploaded_file

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    featured = (
        db.session.execute(
            db.select(Plant)
            .where(Plant.is_available == True, Plant.is_featured == True)
            .order_by(Plant.created_at.desc())
            .limit(8)
        ).scalars().all()
    )
    popular = (
        db.session.execute(
            db.select(Plant)
            .where(Plant.is_available == True, Plant.is_popular == True)
            .order_by(Plant.created_at.desc())
            .limit(8)
        ).scalars().all()
    )
    categories = (
        db.session.execute(
            db.select(Category).where(Category.is_active == True).order_by(Category.display_order)
        ).scalars().all()
    )
    sections = (
        db.session.execute(
            db.select(HomepageSection)
            .where(HomepageSection.is_active == True)
            .order_by(HomepageSection.display_order)
        ).scalars().all()
    )
    return render_template(
        "main/index.html",
        featured=featured,
        popular=popular,
        categories=categories,
        sections=sections,
    )


@bp.route("/plants")
def plants():
    page = request.args.get("page", 1, type=int)
    search = request.args.get("search", "").strip()
    category_id = request.args.get("category", type=int)
    availability = request.args.get("availability", "")
    min_price = request.args.get("min_price", type=float)
    max_price = request.args.get("max_price", type=float)
    sort = request.args.get("sort", "newest")

    query = db.select(Plant).where(Plant.is_available == True)
    if search:
        query = query.where(Plant.name.ilike(f"%{search}%"))
    if category_id:
        query = query.where(Plant.category_id == category_id)
    if availability == "in_stock":
        query = query.where(Plant.stock > 0)
    elif availability == "out_stock":
        query = query.where(Plant.stock <= 0)
    if min_price is not None:
        query = query.where(Plant.price >= min_price)
    if max_price is not None:
        query = query.where(Plant.price <= max_price)

    if sort == "price_asc":
        query = query.order_by(Plant.price.asc())
    elif sort == "price_desc":
        query = query.order_by(Plant.price.desc())
    elif sort == "name_asc":
        query = query.order_by(Plant.name.asc())
    else:
        query = query.order_by(Plant.created_at.desc())

    from app import models as m
    pagination = db.paginate(query, page=page, per_page=12, error_out=False)
    categories = (
        db.session.execute(
            db.select(Category).where(Category.is_active == True).order_by(Category.display_order)
        ).scalars().all()
    )
    return render_template(
        "main/plants.html",
        plants=pagination.items,
        pagination=pagination,
        categories=categories,
        search=search,
        category_id=category_id,
        availability=availability,
        min_price=min_price,
        max_price=max_price,
        sort=sort,
    )


@bp.route("/category/<slug>")
def category_detail(slug):
    category = db.session.execute(
        db.select(Category).where(Category.slug == slug, Category.is_active == True)
    ).scalar_one_or_none()
    if not category:
        abort(404)
    page = request.args.get("page", 1, type=int)
    query = db.select(Plant).where(
        Plant.category_id == category.id, Plant.is_available == True
    ).order_by(Plant.created_at.desc())
    pagination = db.paginate(query, page=page, per_page=12, error_out=False)
    return render_template(
        "main/category.html", category=category, plants=pagination.items, pagination=pagination
    )


@bp.route("/plant/<slug>")
def plant_detail(slug):
    plant = db.session.execute(
        db.select(Plant).where(Plant.slug == slug)
    ).scalar_one_or_none()
    if not plant or not plant.is_available:
        abort(404)
    related = (
        db.session.execute(
            db.select(Plant)
            .where(Plant.category_id == plant.category_id, Plant.id != plant.id, Plant.is_available == True)
            .limit(4)
        ).scalars().all()
    )
    return render_template("main/plant_detail.html", plant=plant, related=related)


@bp.route("/search")
def search():
    q = request.args.get("q", "").strip()
    results = []
    if q:
        results = (
            db.session.execute(
                db.select(Plant)
                .where(Plant.is_available == True, Plant.name.ilike(f"%{q}%"))
                .order_by(Plant.name.asc())
                .limit(30)
            ).scalars().all()
        )
    return render_template("main/search.html", q=q, results=results)


@bp.route("/about")
def about():
    from app.models import WebsiteSetting
    about_text = WebsiteSetting.get_value("about_full", "")
    return render_template("main/about.html", about_text=about_text)


@bp.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        subject = request.form.get("subject", "").strip()
        body = request.form.get("message", "").strip()
        if not name or not email or not body:
            flash("Please fill in all required fields.", "error")
        else:
            msg = Message(
                customer_id=current_user.id if current_user.is_authenticated and current_user.user_type == "customer" else None,
                name=name, email=email, phone=phone, subject=subject, body=body,
            )
            db.session.add(msg)
            db.session.commit()
            # Notify admin
            db.session.add(Notification(
                recipient_type="admin", title="New Contact Message",
                message=f"New message from {name}: {subject}", link="/admin/messages",
                notification_type="message",
            ))
            db.session.commit()
            flash("Thank you! Your message has been sent.", "success")
            return redirect(url_for("main.contact"))
    return render_template("main/contact.html")


@bp.route("/cart", methods=["GET", "POST"])
def cart():
    cart = session.get("cart", {})
    items = []
    total = 0.0
    for pid, data in cart.items():
        plant = db.session.get(Plant, int(pid))
        if not plant:
            continue
        qty = data.get("quantity", 1)
        line_total = float(plant.price) * qty
        total += line_total
        items.append({
            "plant": plant, "quantity": qty, "line_total": line_total,
            "max_stock": plant.stock,
        })
    return render_template("main/cart.html", items=items, total=total)


@bp.route("/cart/add", methods=["POST"])
def cart_add():
    plant_id = request.form.get("plant_id", type=int)
    quantity = request.form.get("quantity", 1, type=int)
    if not plant_id or quantity < 1:
        return jsonify({"success": False, "message": "Invalid request."}), 400
    plant = db.session.get(Plant, plant_id)
    if not plant or not plant.is_available:
        return jsonify({"success": False, "message": "Plant not available."}), 404
    if quantity > plant.stock:
        return jsonify({"success": False, "message": "Not enough stock available."}), 400
    cart = session.get("cart", {})
    key = str(plant_id)
    current_qty = cart.get(key, {}).get("quantity", 0)
    if current_qty + quantity > plant.stock:
        return jsonify({"success": False, "message": "Not enough stock available."}), 400
    cart[key] = {"quantity": current_qty + quantity}
    session["cart"] = cart
    count = sum(i.get("quantity", 0) for i in cart.values())
    return jsonify({"success": True, "message": "Added to cart.", "cart_count": count})


@bp.route("/cart/update", methods=["POST"])
def cart_update():
    plant_id = request.form.get("plant_id", type=int)
    quantity = request.form.get("quantity", type=int)
    cart = session.get("cart", {})
    if plant_id is None or quantity is None:
        return jsonify({"success": False}), 400
    key = str(plant_id)
    if key in cart:
        plant = db.session.get(Plant, plant_id)
        if quantity <= 0:
            cart.pop(key, None)
        else:
            if plant and quantity > plant.stock:
                quantity = plant.stock
            cart[key] = {"quantity": quantity}
        session["cart"] = cart
    return jsonify({"success": True, "cart_count": sum(i.get("quantity", 0) for i in cart.values())})


@bp.route("/cart/remove", methods=["POST"])
def cart_remove():
    plant_id = request.form.get("plant_id", type=int)
    cart = session.get("cart", {})
    if plant_id:
        cart.pop(str(plant_id), None)
        session["cart"] = cart
    return jsonify({"success": True, "cart_count": sum(i.get("quantity", 0) for i in cart.values())})


@bp.route("/notifications")
def notifications():
    if not current_user.is_authenticated or current_user.user_type != "customer":
        return redirect(url_for("auth.login"))
    notes = (
        db.session.execute(
            db.select(Notification)
            .where(Notification.recipient_type == "customer", Notification.recipient_id == current_user.id)
            .order_by(Notification.created_at.desc())
        ).scalars().all()
    )
    return render_template("main/notifications.html", notifications=notes)


@bp.route("/notifications/mark-read", methods=["POST"])
def mark_notifications_read():
    if not current_user.is_authenticated or current_user.user_type != "customer":
        return jsonify({"success": False}), 403
    db.session.execute(
        db.update(Notification)
        .where(Notification.recipient_type == "customer", Notification.recipient_id == current_user.id)
        .values(is_read=True)
    )
    db.session.commit()
    return jsonify({"success": True})
