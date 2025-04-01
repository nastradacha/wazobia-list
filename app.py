import os
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text

# Initialize Flask app
app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-22aa0cd08a839a23a061c102ce4bd644')

# Database configuration
db_uri = os.getenv('DATABASE_URL')
if db_uri and db_uri.startswith('postgres://'):
    db_uri = db_uri.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Configure logging
logging.basicConfig(level=logging.INFO)
app.logger.addHandler(logging.StreamHandler())

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)  # Updated length to 256
    verified = db.Column(db.Boolean, default=False)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

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
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

# Database initialization command
@app.cli.command("init-db")
def init_db():
    """Initialize the database with default categories"""
    with app.app_context():
        try:
            db.create_all()
            default_categories = ['Electronics', 'Furniture', 'Vehicles', 'Fashion']
            for name in default_categories:
                if not Category.query.filter_by(name=name).first():
                    db.session.add(Category(name=name))
                    app.logger.info(f'Added category: {name}')
            db.session.commit()
            app.logger.info('Database initialized successfully')
        except Exception as e:
            app.logger.error(f'Database initialization failed: {str(e)}')
            db.session.rollback()
            raise e

# Login manager setup
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Auth Routes
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        try:
            username = request.form['username']
            email = request.form['email']
            phone = request.form['phone']
            password = request.form['password']
            
            user = User.query.filter(
                (User.username == username) | 
                (User.email == email) | 
                (User.phone == phone)
            ).first()
            
            if user:
                flash('Username, email or phone already exists', 'danger')
                return redirect(url_for('register'))
            
            new_user = User(
                username=username,
                email=email,
                phone=phone
            )
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            flash('Registration successful!', 'success')
            return redirect(url_for('home'))
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'Registration error: {str(e)}')
            flash('Error during registration. Please try again.', 'danger')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        identifier = request.form['identifier']
        password = request.form['password']
        
        user = User.query.filter(
            (User.username == identifier) | 
            (User.email == identifier) | 
            (User.phone == identifier)
        ).first()
        
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('home'))
        
        flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

# Main Routes
@app.route("/")
def home():
    try:
        search_query = request.args.get('q', '')
        category_id = request.args.get('category', type=int)
        
        listings = Listing.query
        if search_query:
            listings = listings.filter(Listing.title.ilike(f'%{search_query}%'))
        if category_id:
            listings = listings.filter_by(category_id=category_id)
        
        categories = Category.query.order_by(Category.name).all()
        
        return render_template(
            "index.html",
            listings=listings.all(),
            categories=categories,
            selected_category=category_id,
            search_query=search_query
        )
        
    except Exception as e:
        app.logger.error(f"Homepage error: {str(e)}")
        flash("Error loading listings. Please try again later.", "danger")
        return redirect(url_for('home'))

@app.route("/post", methods=["POST"])
@login_required
def post_ad():
    try:
        # Convert category_id from string to integer if provided
        category_id = request.form.get("category_id")
        if category_id:
            try:
                category_id = int(category_id)
            except ValueError:
                category_id = None
        else:
            category_id = None

        new_ad = Listing(
            title=request.form["title"],
            price=request.form["price"],
            location=request.form.get("location", "Lagos"),
            description=request.form["description"],
            phone=request.form["phone"],
            category_id=category_id,
            user_id=current_user.id
        )
        db.session.add(new_ad)
        db.session.commit()
        flash("Ad posted successfully!", "success")
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Ad post error: {str(e)}")
        flash(f"Error: {str(e)}", "danger")
    return redirect(url_for("home"))

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_ad(id):
    listing = Listing.query.get_or_404(id)
    
    if listing.user_id != current_user.id:
        abort(403)
    
    if request.method == 'POST':
        try:
            listing.title = request.form["title"]
            listing.price = request.form["price"]
            listing.location = request.form.get("location", "Lagos")
            listing.description = request.form["description"]
            listing.phone = request.form["phone"]
            
            # Convert category_id from string to integer if provided
            category_id = request.form.get("category_id")
            if category_id:
                try:
                    listing.category_id = int(category_id)
                except ValueError:
                    listing.category_id = None
            else:
                listing.category_id = None
            
            db.session.commit()
            flash("Ad updated successfully!", "success")
            return redirect(url_for("home"))
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Ad update error: {str(e)}")
            flash(f"Error updating ad: {str(e)}", "danger")
    
    categories = Category.query.all()
    return render_template("edit.html", listing=listing, categories=categories)

@app.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete_ad(id):
    listing = Listing.query.get_or_404(id)
    
    if listing.user_id != current_user.id:
        abort(403)
    
    try:
        db.session.delete(listing)
        db.session.commit()
        flash("Ad deleted successfully!", "success")
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Ad delete error: {str(e)}")
        flash(f"Error deleting ad: {str(e)}", "danger")
    
    return redirect(url_for("home"))


@app.route('/migration-version')
def migration_version():
    result = db.session.execute(text("SELECT version_num FROM alembic_version"))
    version = result.fetchone()[0]
    return f"Current migration revision: {version}"

@app.route('/check-password-hash-length')
def check_password_hash_length():
    result = db.session.execute(text(
        "SELECT character_maximum_length FROM information_schema.columns "
        "WHERE table_name = 'user' AND column_name = 'password_hash';"))
    length = result.fetchone()[0]
    return f"password_hash column length: {length}"

if __name__ == "__main__":
    app.run()
