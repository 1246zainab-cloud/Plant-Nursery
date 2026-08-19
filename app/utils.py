import os
import secrets
import string
from datetime import datetime, timezone

from flask import current_app


def utcnow():
    """Return a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def format_currency(value):
    """Format a number as currency (USD)."""
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "$0.00"


def format_datetime(dt):
    """Format a datetime for display."""
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%b %d, %Y %I:%M %p")


def format_date(dt):
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%b %d, %Y")


def generate_secure_filename(original_filename):
    """Generate a safe, unique filename preserving the extension."""
    if not original_filename:
        return None
    ext = os.path.splitext(original_filename)[1].lower()
    alphabet = string.ascii_letters + string.digits
    rand = "".join(secrets.choice(alphabet) for _ in range(16))
    return f"{rand}{ext}"


def allowed_file(filename, allowed=None):
    """Check if the uploaded file has an allowed extension."""
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    if allowed is None:
        allowed = current_app.config.get("ALLOWED_EXTENSIONS", set())
    return ext in allowed


def save_uploaded_file(file_storage, subfolder=""):
    """Save an uploaded file to the uploads directory and return the relative URL path."""
    from flask import current_app
    from werkzeug.utils import secure_filename

    if not file_storage:
        return None
    filename = generate_secure_filename(file_storage.filename)
    if not filename:
        return None
    upload_dir = current_app.config["UPLOAD_FOLDER"]
    if subfolder:
        upload_dir = os.path.join(upload_dir, subfolder)
    os.makedirs(upload_dir, exist_ok=True)
    dest = os.path.join(upload_dir, filename)
    file_storage.save(dest)
    # Return a URL path usable in templates
    rel = os.path.relpath(dest, os.path.join(BASE_DIR := os.path.abspath(os.path.join(upload_dir, "..", "..", "..")), "app", "static"))
    # Simpler: build path relative to static
    static_root = os.path.abspath(os.path.join(current_app.root_path, "static"))
    rel_path = os.path.relpath(dest, static_root)
    rel_path = rel_path.replace("\\", "/")
    return "/" + rel_path


def delete_uploaded_file(relative_path):
    """Delete a previously uploaded file given its relative URL path."""
    if not relative_path:
        return
    from flask import current_app
    static_root = os.path.abspath(os.path.join(current_app.root_path, "static"))
    # relative_path like /uploads/xxx.png
    clean = relative_path.lstrip("/")
    full = os.path.join(static_root, clean)
    try:
        if os.path.isfile(full):
            os.remove(full)
    except Exception:
        pass


def slugify(text):
    """Create a URL-friendly slug."""
    text = text.lower().strip()
    out = []
    for ch in text:
        if ch.isalnum():
            out.append(ch)
        elif ch == " ":
            out.append("-")
    return "".join(out)
