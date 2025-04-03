import os
import logging
import random
from datetime import datetime, timedelta
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, abort, session
)
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import (
    LoginManager, UserMixin, login_user,
    logout_user, login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text, Index, or_
from sqlalchemy.orm import joinedload
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# ---------------------------- #
#      Extension Initialization #
# ---------------------------- #

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
limiter = Limiter(storage_uri="memory://", key_func=get_remote_address)

# ---------------------------- #
#      Database Models         #
# ---------------------------- #

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    verified = db.Column(db.Boolean, default=False)
    listings = db.relationship('Listing', backref='user', lazy=True)
    
    def __repr__(self):
        return f'<User {self.username}>'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

Index('ix_user_credentials', User.username, User.email, User.phone)

class Category(db.Model):
    __tablename__ = 'categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    listings = db.relationship('Listing', backref='category', lazy=True)
    
    def __repr__(self):
        return f'<Category {self.name}>'

class Listing(db.Model):
    __tablename__ = 'listings'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False, index=True)
    price = db.Column(db.String(20))
    description = db.Column(db.Text)
    location = db.Column(db.String(50), default='Lagos')
    phone = db.Column(db.String(20), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Listing {self.title}>'

class OTPVerification(db.Model):
    __tablename__ = 'otp_verifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    otp = db.Column(db.String(6), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)
    
    def __repr__(self):
        return f'<OTPVerification {self.user_id}>'

# ---------------------------- #
#      Application Factory      #
# ---------------------------- #

def create_app(config_overrides=None):
    app = Flask(__name__)
    
    # Configure application
    app.config.update(
        SECRET_KEY=os.getenv('SECRET_KEY', 'dev-secret-key-22aa0cd08a839a23a061c102ce4bd644'),
        SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URL', 
    'postgresql://wazobia_db_pjpf_user:sN2H8Wzmv32eP8BQPzQpQ2pWTUKwmiUr@dpg-cvmslo7gi27c73bcsuug-a.oregon-postgres.render.com:5432/wazobia_db_pjpf'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=os.getenv('FLASK_ENV') == 'production',
        PERMANENT_SESSION_LIFETIME=timedelta(hours=2),
        SQLALCHEMY_ENGINE_OPTIONS={
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }
    )

    if config_overrides:
        app.config.update(config_overrides)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    limiter.init_app(app) 

    # Configure login manager
    login_manager.login_view = 'login'

    # Initialize logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Register routes
    with app.app_context():
        register_routes(app)
        register_cli(app)
        register_error_handlers(app)

    return app

# ---------------------------- #
#      Helper Functions         #
# ---------------------------- #

def generate_otp() -> str:
    return str(random.randint(100000, 999999))

def send_otp_via_email(email: str, otp: str) -> bool:
    logger = logging.getLogger(__name__)
    try:
        logger.info(f"OTP for {email}: {otp}")
        return True
    except Exception as e:
        logger.error(f"Email send failed: {str(e)}")
        return False

def cleanup_expired_otps():
    logger = logging.getLogger(__name__)
    try:
        expired = OTPVerification.query.filter(
            OTPVerification.expires_at < datetime.utcnow()
        ).delete()
        db.session.commit()
        logger.info(f"Cleaned up {expired} expired OTPs")
    except Exception as e:
        db.session.rollback()
        logger.error(f"OTP cleanup failed: {str(e)}")

# ---------------------------- #
#      Route Registration       #
# ---------------------------- #

def register_routes(app):
    @app.route('/')
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
            
            return render_template("index.html", listings=listings.all(),
                                   categories=categories, selected_category=category_id,
                                   search_query=search_query)
        except Exception as e:
            app.logger.error(f"Homepage error: {str(e)}")
            flash("Error loading listings. Please try again later.", "danger")
            return redirect(url_for('home'))

    # Add all other route definitions here following the same pattern
    # (Login, logout, register, etc. - maintain original route code)
    # ... [rest of your route definitions] ...

# ---------------------------- #
#      Error Handlers           #
# ---------------------------- #

def register_error_handlers(app):
    @app.errorhandler(503)
    def service_unavailable(e):
        return render_template('503.html'), 503

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('403.html'), 403

    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        return render_template('500.html'), 500

# ---------------------------- #
#      CLI Commands             #
# ---------------------------- #

def register_cli(app):
    @app.cli.command("seed-categories")
    def seed_categories():
        default_categories = ['Electronics', 'Furniture', 'Vehicles', 'Fashion']
        try:
            for name in default_categories:
                if not Category.query.filter_by(name=name).first():
                    db.session.add(Category(name=name))
            db.session.commit()
            logging.info("Categories seeded successfully")
        except Exception as e:
            db.session.rollback()
            logging.error(f"Category seeding failed: {str(e)}")

# ---------------------------- #
#      Login Manager Setup      #
# ---------------------------- #

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ---------------------------- #
#      Application Entry        #
# ---------------------------- #

if __name__ == "__main__":
    app = create_app()
    app.run()