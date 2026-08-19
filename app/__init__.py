from flask import Flask, session, g, request
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFProtect

from app.extensions import db, login_manager
from config import config_map

csrf = CSRFProtect()


def create_app(config_name="default"):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_map[config_name])

    # Ensure upload folder exists
    import os
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "info"
    csrf.init_app(app)

    from app import models  # noqa: F401  (register models)

    _register_user_loader(app)
    _register_context_processors(app)
    _register_template_filters(app)
    _register_error_handlers(app)
    _register_blueprints(app)

    with app.app_context():
        db.create_all()
        _seed_initial_data(app)

    return app


def _register_user_loader(app):
    from app.models import Admin, Staff, Customer

    @login_manager.user_loader
    def load_user(user_id):
        # user_id format: "type:id"
        try:
            user_type, uid = user_id.split(":", 1)
        except ValueError:
            return None
        if user_type == "admin":
            return db.session.get(Admin, int(uid))
        if user_type == "staff":
            return db.session.get(Staff, int(uid))
        if user_type == "customer":
            return db.session.get(Customer, int(uid))
        return None


def _register_context_processors(app):
    from app.models import (
        WebsiteSetting, NavigationItem, SocialLink, FooterContent,
        Announcement, Category, Plant, Banner, Notification, Message,
    )

    @app.context_processor
    def inject_site_data():
        site = {
            "name": WebsiteSetting.get_value("site_name", "GreenLeaf Nursery"),
            "logo": WebsiteSetting.get_value("logo", ""),
            "favicon": WebsiteSetting.get_value("favicon", ""),
            "tagline": WebsiteSetting.get_value("tagline", "Grow with nature"),
            "about_short": WebsiteSetting.get_value("about_short", ""),
        }
        nav_items = (
            db.session.execute(
                db.select(NavigationItem)
                .where(NavigationItem.is_active == True, NavigationItem.location == "main")
                .order_by(NavigationItem.display_order)
            ).scalars().all()
        )
        footer_nav = (
            db.session.execute(
                db.select(NavigationItem)
                .where(NavigationItem.is_active == True, NavigationItem.location == "footer")
                .order_by(NavigationItem.display_order)
            ).scalars().all()
        )
        social_links = (
            db.session.execute(
                db.select(SocialLink)
                .where(SocialLink.is_active == True)
                .order_by(SocialLink.display_order)
            ).scalars().all()
        )
        footer = db.session.execute(db.select(FooterContent)).scalars().first()
        announcements = (
            db.session.execute(
                db.select(Announcement)
                .where(Announcement.is_active == True)
                .order_by(Announcement.display_order)
            ).scalars().all()
        )
        categories = (
            db.session.execute(
                db.select(Category)
                .where(Category.is_active == True)
                .order_by(Category.display_order)
            ).scalars().all()
        )
        banners = (
            db.session.execute(
                db.select(Banner)
                .where(Banner.is_active == True)
                .order_by(Banner.display_order)
            ).scalars().all()
        )

        # Cart (session based)
        cart = session.get("cart", {})
        cart_count = sum(item.get("quantity", 0) for item in cart.values())

        # Notifications for logged-in customer
        notifications = []
        unread_notifications = 0
        unread_messages = 0
        if current_user.is_authenticated:
            if current_user.user_type == "customer":
                notifications = (
                    db.session.execute(
                        db.select(Notification)
                        .where(
                            Notification.recipient_type == "customer",
                            Notification.recipient_id == current_user.id,
                        )
                        .order_by(Notification.created_at.desc())
                        .limit(10)
                    ).scalars().all()
                )
                unread_notifications = (
                    db.session.execute(
                        db.select(db.func.count(Notification.id)).where(
                            Notification.recipient_type == "customer",
                            Notification.recipient_id == current_user.id,
                            Notification.is_read == False,
                        )
                    ).scalar() or 0
                )
            elif current_user.user_type in ("admin", "staff"):
                unread_messages = (
                    db.session.execute(
                        db.select(db.func.count(Message.id)).where(Message.is_read == False)
                    ).scalar() or 0
                )
                notifications = (
                    db.session.execute(
                        db.select(Notification)
                        .where(Notification.recipient_type == "admin")
                        .order_by(Notification.created_at.desc())
                        .limit(10)
                    ).scalars().all()
                )
                unread_notifications = (
                    db.session.execute(
                        db.select(db.func.count(Notification.id)).where(
                            Notification.recipient_type == "admin",
                            Notification.is_read == False,
                        )
                    ).scalar() or 0
                )

        return dict(
            site=site,
            nav_items=nav_items,
            footer_nav=footer_nav,
            social_links=social_links,
            footer=footer,
            announcements=announcements,
            categories=categories,
            banners=banners,
            cart_count=cart_count,
            notifications=notifications,
            unread_notifications=unread_notifications,
            unread_messages=unread_messages,
        )


def _register_template_filters(app):
    from app.utils import format_currency, format_datetime, format_date

    app.jinja_env.filters["currency"] = format_currency
    app.jinja_env.filters["datetime"] = format_datetime
    app.jinja_env.filters["date"] = format_date


def _register_error_handlers(app):
    from flask import render_template

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(500)
    def server_error(e):
        return render_template("errors/500.html"), 500

    @app.errorhandler(413)
    def file_too_large(e):
        from flask import flash, redirect, request, url_for
        flash("Uploaded file is too large.", "error")
        return redirect(request.referrer or url_for("main.index"))


def _register_blueprints(app):
    from app.routes import main, auth, customer, admin

    app.register_blueprint(main.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(customer.bp)
    app.register_blueprint(admin.bp)


def _seed_initial_data(app):
    """Create default admin and base website settings if they don't exist."""
    from app.models import Admin, WebsiteSetting, NavigationItem, FooterContent, SocialLink, Category

    # Default admin
    if not db.session.execute(db.select(Admin).limit(1)).scalar_one_or_none():
        admin = Admin(
            username=app.config.get("ADMIN_USERNAME", "admin"),
            email=app.config.get("ADMIN_EMAIL", "admin@nursery.com"),
            full_name="System Administrator",
            is_super=True,
        )
        admin.set_password(app.config.get("ADMIN_PASSWORD", "admin123"))
        db.session.add(admin)
        db.session.commit()

    # Default website settings
    defaults = {
        "site_name": "GreenLeaf Nursery",
        "tagline": "Grow with nature",
        "about_short": "GreenLeaf Nursery is your trusted partner for healthy plants, expert advice, and beautiful greenery for every space.",
        "logo": "",
        "favicon": "",
        "contact_address": "123 Garden Avenue, Green City",
        "contact_phone": "+1 (555) 123-4567",
        "contact_email": "hello@greenleafnursery.com",
        "footer_about": "GreenLeaf Nursery brings nature to your doorstep with premium plants and expert care.",
        "copyright": "© 2024 GreenLeaf Nursery. All rights reserved.",
    }
    for k, v in defaults.items():
        if not WebsiteSetting.get_value(k):
            WebsiteSetting.set_value(k, v)

    # Default navigation
    if not db.session.execute(db.select(NavigationItem).limit(1)).scalar_one_or_none():
        defaults_nav = [
            ("Home", "/", 1),
            ("Plants", "/plants", 2),
            ("Categories", "/categories", 3),
            ("About Us", "/about", 4),
            ("Contact Us", "/contact", 5),
        ]
        for label, url, order in defaults_nav:
            db.session.add(NavigationItem(label=label, url=url, display_order=order, location="main"))
        footer_links = [
            ("Home", "/", 1),
            ("Plants", "/plants", 2),
            ("Categories", "/categories", 3),
            ("About Us", "/about", 4),
            ("Contact Us", "/contact", 5),
            ("My Account", "/customer/profile", 6),
        ]
        for label, url, order in footer_links:
            db.session.add(NavigationItem(label=label, url=url, display_order=order, location="footer"))
        db.session.commit()

    # Default footer
    if not db.session.execute(db.select(FooterContent).limit(1)).scalar_one_or_none():
        db.session.add(FooterContent(
            about_text=defaults["footer_about"],
            copyright_text=defaults["copyright"],
            contact_address=defaults["contact_address"],
            contact_phone=defaults["contact_phone"],
            contact_email=defaults["contact_email"],
        ))
        db.session.commit()

    # Default social links
    if not db.session.execute(db.select(SocialLink).limit(1)).scalar_one_or_none():
        for i, (platform, url) in enumerate([
            ("facebook", "https://facebook.com"),
            ("instagram", "https://instagram.com"),
            ("twitter", "https://twitter.com"),
            ("youtube", "https://youtube.com"),
        ], start=1):
            db.session.add(SocialLink(platform=platform, url=url, display_order=i))
        db.session.commit()

    # Default categories
    if not db.session.execute(db.select(Category).limit(1)).scalar_one_or_none():
        from app.utils import slugify
        names = [
            "Indoor Plants", "Outdoor Plants", "Flowering Plants", "Medicinal Plants",
            "Herbs", "Fruit Plants", "Vegetable Plants", "Succulents", "Ornamental Plants",
        ]
        for i, name in enumerate(names, start=1):
            db.session.add(Category(name=name, slug=slugify(name), display_order=i))
        db.session.commit()
