
from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
import os
import uuid
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "lostlink_secret_key"

DATABASE = os.path.join(app.root_path, "database.db")

UPLOAD_FOLDER = os.path.join(app.root_path, "static", "uploads")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# Check allowed image extensions
def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


# Database connection
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# Create database and update existing table
def create_table():
    conn = get_db_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            location TEXT,
            contact TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Add image column if it does not exist
    columns = [
        row["name"]
        for row in conn.execute("PRAGMA table_info(items)").fetchall()
    ]

    if "image" not in columns:
        conn.execute("ALTER TABLE items ADD COLUMN image TEXT")

    conn.commit()
    conn.close()


# Homepage
@app.route("/")
def index():

    search = request.args.get("search", "").strip()
    category = request.args.get("category", "")

    conn = get_db_connection()

    query = "SELECT * FROM items WHERE name LIKE ?"
    params = ["%" + search + "%"]

    if category in ["Lost", "Found"]:
        query += " AND category = ?"
        params.append(category)

    query += " ORDER BY id DESC"

    items = conn.execute(query, params).fetchall()

    conn.close()

    return render_template(
        "index.html",
        items=items,
        search=search,
        category=category
    )


# Add item
@app.route("/add", methods=["GET", "POST"])
def add_item():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        category = request.form.get("category", "")
        description = request.form.get("description", "").strip()
        location = request.form.get("location", "").strip()
        contact = request.form.get("contact", "").strip()

        image = request.files.get("image")
        image_filename = None

        if not name or not contact or category not in ["Lost", "Found"]:
            flash("Please enter valid item details.", "error")
            return redirect(url_for("add_item"))

        # Handle image upload
        if image and image.filename:

            if not allowed_file(image.filename):
                flash("Only JPG, JPEG, PNG and WEBP images are allowed.", "error")
                return redirect(url_for("add_item"))

            original_name = secure_filename(image.filename)
            extension = original_name.rsplit(".", 1)[1].lower()

            image_filename = f"{uuid.uuid4().hex}.{extension}"

            image.save(
                os.path.join(UPLOAD_FOLDER, image_filename)
            )

        conn = get_db_connection()

        conn.execute("""
            INSERT INTO items
            (name, category, description, location, contact, image)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            name,
            category,
            description,
            location,
            contact,
            image_filename
        ))

        conn.commit()
        conn.close()

        flash("Your item has been reported successfully!", "success")

        return redirect(url_for("index"))

    return render_template("add_item.html")


# Mark item as returned
@app.route("/return/<int:item_id>", methods=["POST"])
def mark_returned(item_id):

    conn = get_db_connection()

    conn.execute(
        "UPDATE items SET status = 'Returned' WHERE id = ?",
        (item_id,)
    )

    conn.commit()
    conn.close()

    flash("Item marked as returned!", "success")

    return redirect(url_for("index"))


# Delete item and its uploaded image
@app.route("/delete/<int:item_id>", methods=["POST"])
def delete_item(item_id):

    conn = get_db_connection()

    item = conn.execute(
        "SELECT image FROM items WHERE id = ?",
        (item_id,)
    ).fetchone()

    if item:
        if item["image"]:
            image_path = os.path.join(
                UPLOAD_FOLDER, item["image"]
            )

            if os.path.isfile(image_path):
                os.remove(image_path)

        conn.execute(
            "DELETE FROM items WHERE id = ?",
            (item_id,)
        )

        conn.commit()
        flash("Item deleted successfully!", "success")

    conn.close()

    return redirect(url_for("index"))


# Handle oversized uploads
@app.errorhandler(413)
def file_too_large(error):
    flash("Image is too large. Maximum size is 5 MB.", "error")
    return redirect(url_for("add_item"))


if __name__ == "__main__":
    create_table()
    app.run(debug=True)
