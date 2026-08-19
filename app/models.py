from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db
from app.utils import utcnow


# ---------------------------------------------------------------------------
# Authentication / Users
# ---------------------------------------------------------------------------

class Admin(UserMixin, db.Model):
    __tablename__ = "admins"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120), default="")
    phone = db.Column(db.String(40), default="")
    is_super = db.Column(db.Boolean, default=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        return f"admin:{self.id}"

    @property
    def user_type(self):
        return "admin"


class Staff(UserMixin, db.Model):
    __tablename__ = "staff"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120), default="")
    phone = db.Column(db.String(40), default="")
    role = db.Column(db.String(60), default="Staff")
    permissions = db.Column(db.Text, default="")  # comma separated keys
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def has_permission(self, key):
        if not self.is_active:
            return False
        perms = [p.strip() for p in (self.permissions or "").split(",") if p.strip()]
        return "all" in perms or key in perms

    def get_id(self):
        return f"staff:{self.id}"

    @property
    def user_type(self):
        return "staff"


class Customer(UserMixin, db.Model):
    __tablename__ = "customers"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120), default="")
    phone = db.Column(db.String(40), default="")
    address = db.Column(db.Text, default="")
    city = db.Column(db.String(80), default="")
    state = db.Column(db.String(80), default="")
    zip_code = db.Column(db.String(20), default="")
    country = db.Column(db.String(80), default="")
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        return f"customer:{self.id}"

    @property
    def user_type(self):
        return "customer"

    @property
    def orders_count(self):
        return Order.query.filter_by(customer_id=self.id).count()


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.Text, default="")
    image = db.Column(db.String(255), default="")
    is_active = db.Column(db.Boolean, default=True)
    display_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    plants = db.relationship("Plant", backref="category", lazy="dynamic")

    def __repr__(self):
        return f"<Category {self.name}>"


class Plant(db.Model):
    __tablename__ = "plants"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, index=True)
    slug = db.Column(db.String(170), unique=True, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False, index=True)
    description = db.Column(db.Text, default="")
    short_description = db.Column(db.String(300), default="")
    price = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    stock = db.Column(db.Integer, nullable=False, default=0)
    is_available = db.Column(db.Boolean, default=True)
    is_featured = db.Column(db.Boolean, default=False)
    is_popular = db.Column(db.Boolean, default=False)
    plant_type = db.Column(db.String(80), default="")
    size = db.Column(db.String(80), default="")
    care_instructions = db.Column(db.Text, default="")
    watering_requirements = db.Column(db.Text, default="")
    sunlight_requirements = db.Column(db.Text, default="")
    image = db.Column(db.String(255), default="")
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    order_items = db.relationship("OrderItem", backref="plant", lazy="dynamic")

    @property
    def in_stock(self):
        return self.is_available and self.stock > 0

    @property
    def price_float(self):
        return float(self.price)

    def __repr__(self):
        return f"<Plant {self.name}>"


class InventoryLog(db.Model):
    __tablename__ = "inventory"
    id = db.Column(db.Integer, primary_key=True)
    plant_id = db.Column(db.Integer, db.ForeignKey("plants.id"), nullable=False, index=True)
    change = db.Column(db.Integer, nullable=False)  # positive add, negative deduct
    previous_stock = db.Column(db.Integer, default=0)
    new_stock = db.Column(db.Integer, default=0)
    reason = db.Column(db.String(120), default="")
    reference = db.Column(db.String(120), default="")  # order id etc.
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    plant = db.relationship("Plant", backref="inventory_logs", lazy="joined")


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------

ORDER_STATUS = ["Pending", "Confirmed", "Processing", "Ready", "Completed", "Cancelled"]


class Order(db.Model):
    __tablename__ = "orders"
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(40), unique=True, nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False, index=True)
    status = db.Column(db.String(30), default="Pending", index=True)
    subtotal = db.Column(db.Numeric(10, 2), default=0)
    total = db.Column(db.Numeric(10, 2), default=0)
    payment_method = db.Column(db.String(30), default="Cash on Delivery")
    shipping_address = db.Column(db.Text, default="")
    contact_phone = db.Column(db.String(40), default="")
    notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, index=True)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    customer = db.relationship("Customer", backref="orders", lazy="joined")
    items = db.relationship("OrderItem", backref="order", lazy="dynamic", cascade="all, delete-orphan")

    @property
    def total_quantity(self):
        return sum(item.quantity for item in self.items)


class OrderItem(db.Model):
    __tablename__ = "order_items"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False, index=True)
    plant_id = db.Column(db.Integer, db.ForeignKey("plants.id"), nullable=False, index=True)
    plant_name = db.Column(db.String(150), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    @property
    def line_total(self):
        return float(self.unit_price) * self.quantity


class Sale(db.Model):
    """Denormalized sales records for fast reporting."""
    __tablename__ = "sales"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False, index=True)
    order_item_id = db.Column(db.Integer, db.ForeignKey("order_items.id"), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False, index=True)
    plant_id = db.Column(db.Integer, db.ForeignKey("plants.id"), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True, index=True)
    plant_name = db.Column(db.String(150), nullable=False, default="")
    customer_name = db.Column(db.String(150), nullable=False, default="")
    order_number = db.Column(db.String(50), nullable=False, default="")
    unit_price = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    amount = db.Column(db.Numeric(10, 2), default=0)
    status = db.Column(db.String(30), default="Pending")
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, index=True)

    order = db.relationship("Order", backref="sales", lazy="joined")
    plant = db.relationship("Plant", backref="sales", lazy="joined")
    category = db.relationship("Category", backref="sales", lazy="joined")
    customer = db.relationship("Customer", backref="sales", lazy="joined")


# ---------------------------------------------------------------------------
# Suppliers
# ---------------------------------------------------------------------------

class Supplier(db.Model):
    __tablename__ = "suppliers"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, index=True)
    contact_person = db.Column(db.String(120), default="")
    phone = db.Column(db.String(40), default="")
    email = db.Column(db.String(120), default="")
    address = db.Column(db.Text, default="")
    supplied_products = db.Column(db.Text, default="")
    notes = db.Column(db.Text, default="")
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)


# ---------------------------------------------------------------------------
# Communication
# ---------------------------------------------------------------------------

class Message(db.Model):
    __tablename__ = "messages"
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=True, index=True)
    name = db.Column(db.String(120), default="")
    email = db.Column(db.String(120), default="")
    phone = db.Column(db.String(40), default="")
    subject = db.Column(db.String(200), default="")
    body = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    admin_reply = db.Column(db.Text, default="")
    replied_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, index=True)

    customer = db.relationship("Customer", backref="messages", lazy="joined")


class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    recipient_type = db.Column(db.String(20), default="customer")  # customer, admin, staff
    recipient_id = db.Column(db.Integer, nullable=True, index=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, default="")
    link = db.Column(db.String(255), default="")
    is_read = db.Column(db.Boolean, default=False)
    notification_type = db.Column(db.String(40), default="system")
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, index=True)


# ---------------------------------------------------------------------------
# Website content / dynamic management
# ---------------------------------------------------------------------------

class WebsiteSetting(db.Model):
    """Key-value store for global website settings."""
    __tablename__ = "website_settings"
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False, index=True)
    value = db.Column(db.Text, default="")
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    @classmethod
    def get_value(cls, key, default=""):
        row = db.session.execute(db.select(cls).where(cls.key == key)).scalar_one_or_none()
        return row.value if row else default

    @classmethod
    def set_value(cls, key, value):
        row = db.session.execute(db.select(cls).where(cls.key == key)).scalar_one_or_none()
        if row:
            row.value = value
        else:
            row = cls(key=key, value=value)
            db.session.add(row)
        db.session.commit()
        return row


class NavigationItem(db.Model):
    __tablename__ = "navigation_items"
    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(255), nullable=False)
    display_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    location = db.Column(db.String(20), default="main")  # main, footer
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)


class Banner(db.Model):
    __tablename__ = "banners"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), default="")
    description = db.Column(db.Text, default="")
    image = db.Column(db.String(255), default="")
    cta_text = db.Column(db.String(80), default="")
    cta_link = db.Column(db.String(255), default="")
    is_active = db.Column(db.Boolean, default=True)
    display_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class HomepageSection(db.Model):
    __tablename__ = "homepage_sections"
    id = db.Column(db.Integer, primary_key=True)
    section_type = db.Column(db.String(40), default="custom")  # hero, featured, categories, popular, about, announcements, custom
    title = db.Column(db.String(200), default="")
    description = db.Column(db.Text, default="")
    image = db.Column(db.String(255), default="")
    button_text = db.Column(db.String(80), default="")
    button_link = db.Column(db.String(255), default="")
    is_active = db.Column(db.Boolean, default=True)
    display_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class FooterContent(db.Model):
    __tablename__ = "footer_content"
    id = db.Column(db.Integer, primary_key=True)
    about_text = db.Column(db.Text, default="")
    copyright_text = db.Column(db.String(255), default="")
    contact_address = db.Column(db.Text, default="")
    contact_phone = db.Column(db.String(60), default="")
    contact_email = db.Column(db.String(120), default="")
    show_categories = db.Column(db.Boolean, default=True)
    show_quick_links = db.Column(db.Boolean, default=True)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class SocialLink(db.Model):
    __tablename__ = "social_links"
    id = db.Column(db.Integer, primary_key=True)
    platform = db.Column(db.String(40), nullable=False)  # facebook, twitter, instagram, youtube, linkedin
    url = db.Column(db.String(255), default="")
    is_active = db.Column(db.Boolean, default=True)
    display_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)


class Announcement(db.Model):
    __tablename__ = "announcements"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, default="")
    is_active = db.Column(db.Boolean, default=True)
    display_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)
