import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# Initialize Flask app
app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-22aa0cd08a839a23a061c102ce4bd644')  # Development fallback

# Database configuration
db_uri = os.getenv('DATABASE_URL', 'sqlite:///site.db')
if db_uri.startswith('postgres://'):
    db_uri = db_uri.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# production session cleanup
@app.teardown_appcontext
def shutdown_session(exception=None):
    db.session.remove()

# Database Models
class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    listings = db.relationship('Listing', backref='category', lazy=True)

class Listing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    price = db.Column(db.String(20))
    description = db.Column(db.Text)
    location = db.Column(db.String(50), default='Lagos')
    phone = db.Column(db.String(20), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))

# CLI Commands
@app.cli.command("init-db")
def init_db():
    """Initialize the database with default categories"""
    with app.app_context():
        db.create_all()
        
        # Add default categories if none exist
        if not Category.query.first():
            categories = ['Electronics', 'Furniture', 'Vehicles', 'Fashion']
            for name in categories:
                if not Category.query.filter_by(name=name).first():
                    db.session.add(Category(name=name))
            db.session.commit()
            print("Database initialized with default categories!")

# Routes
@app.route("/")
def home():
    search_query = request.args.get('q', '')
    category_id = request.args.get('category', type=int)
    
    listings = Listing.query
    if search_query:
        listings = listings.filter(Listing.title.contains(search_query))
    if category_id:
        listings = listings.filter_by(category_id=category_id)
    
    return render_template(
        "index.html",
        listings=listings.all(),
        categories=Category.query.all(),
        selected_category=category_id,
        search_query=search_query
    )

@app.route("/post", methods=["POST"])
def post_ad():
    try:
        new_ad = Listing(
            title=request.form["title"],
            price=request.form["price"],
            location=request.form.get("location", "Lagos"),
            description=request.form["description"],
            phone=request.form["phone"],
            category_id=request.form.get("category_id")
        )
        db.session.add(new_ad)
        db.session.commit()
        flash("Ad posted successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error: {str(e)}", "danger")
    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run()