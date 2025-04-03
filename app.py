import os
import logging
import random
import requests
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, abort, session
from dotenv import load_dotenv
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
#      Extension Initialization
# ---------------------------- #

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
limiter = Limiter(storage_uri="memory://", key_func=get_remote_address)

# ---------------------------- #
#      Database Models
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
#      Application Factory
# ---------------------------- #

def create_app(config_overrides=None):
    app = Flask(__name__)
    
    load_dotenv()  # load local .env if present
    
    app.config.update(
        SECRET_KEY=os.getenv('SECRET_KEY', 'dev-secret-key'),
        SQLALCHEMY_DATABASE_URI=os.getenv(
            'DATABASE_URL', 
            'postgresql://wazobia_db_pjpf_user:password@localhost:5432/wazobia_db'
        ),
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
    print(f"Using database: {app.config['SQLALCHEMY_DATABASE_URI']}")
    if config_overrides:
        app.config.update(config_overrides)
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    limiter.init_app(app)
    
    # Configure login manager
    login_manager.login_view = 'login'
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Register routes, CLI commands, and error handlers
    with app.app_context():
        register_routes(app)
        register_cli(app)
        register_error_handlers(app)
    
    return app

# ---------------------------- #
#      Helper Functions
# ---------------------------- #

def generate_otp() -> str:
    return str(random.randint(100000, 999999))

def send_otp_via_email(email: str, otp: str) -> bool:
    """
    Sends OTP via Mailgun.
    Expects MAILGUN_API_KEY, MAILGUN_DOMAIN, and EMAIL_FROM to be set in environment variables.
    """
    logger = logging.getLogger(__name__)
    try:
        mailgun_api_key = os.environ.get("MAILGUN_API_KEY")
        mailgun_domain = os.environ.get("MAILGUN_DOMAIN")
        from_email = os.environ.get("EMAIL_FROM", "no-reply@yourdomain.com")
        
        subject = "Your OTP Code for Wazobia List"
        text_content = f"Your OTP is: {otp}. It will expire in 10 minutes."
        
        response = requests.post(
            f"https://api.mailgun.net/v3/{mailgun_domain}/messages",
            auth=("api", mailgun_api_key),
            data={
                "from": from_email,
                "to": email,
                "subject": subject,
                "text": text_content,
            },
        )
        
        logger.info(f"Sent OTP to {email}: Status {response.status_code}")
        return 200 <= response.status_code < 300
    except Exception as e:
        logger.error(f"Mailgun error: {str(e)}")
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
#      Route Registration
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
    
    @app.route('/post', methods=["POST"])
    @login_required
    def post_ad():
        try:
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
    
        categories = Category.query.order_by(Category.name).all()
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
    
    @app.route('/list-categories')
    def list_categories():
        categories = Category.query.order_by(Category.name).all()
        return ", ".join([f"{cat.id}: {cat.name}" for cat in categories])
    
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
    
    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for('home'))
    
        if request.method == 'POST':
            username = request.form.get('username')
            email = request.form.get('email')
            phone = request.form.get('phone')
            password = request.form.get('password')
    
            existing_user = User.query.filter(
                (User.username == username) | 
                (User.email == email) | 
                (User.phone == phone)
            ).first()
            if existing_user:
                flash("A user with these details already exists.", "danger")
                return redirect(url_for('register'))
    
            new_user = User(username=username, email=email, phone=phone)
            new_user.set_password(password)
    
            try:
                db.session.add(new_user)
                db.session.commit()
                flash("Registration successful! Please login and verify your phone.", "success")
                return redirect(url_for('login'))
            except Exception as e:
                db.session.rollback()
                app.logger.error(f"Registration error: {str(e)}")
                flash("Error during registration. Please try again.", "danger")
    
        return render_template('register.html')
    
    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        return redirect(url_for('home'))
    
    # ------------------------------- #
    #       OTP Verification Routes
    # ------------------------------- #
    
    @app.route('/send-otp')
    @login_required
    def send_otp():
        if current_user.verified:
            flash("Your phone number is already verified.", "info")
            return redirect(url_for('home'))
        # Remove any unused OTPs for the user
        OTPVerification.query.filter_by(user_id=current_user.id, used=False).delete()
        db.session.commit()
        otp = generate_otp()
        expires_at = datetime.utcnow() + timedelta(minutes=10)
        new_otp = OTPVerification(user_id=current_user.id, otp=otp, expires_at=expires_at)
        db.session.add(new_otp)
        db.session.commit()
        # Send OTP via Mailgun
        if send_otp_via_email(current_user.email, otp):
            flash("OTP has been sent to your email address.", "info")
        else:
            flash("Failed to send OTP. Please try again.", "danger")
        return redirect(url_for('verify_otp'))
    
    @app.route('/verify-otp', methods=['GET', 'POST'])
    @login_required
    def verify_otp():
        if current_user.verified:
            flash("Your phone number is already verified.", "info")
            return redirect(url_for('home'))
        if request.method == 'POST':
            user_input = request.form.get('otp')
            if not user_input:
                flash("Please enter the OTP.", "warning")
                return redirect(url_for('verify_otp'))
            # Look up an OTP record that matches the user and the input
            otp_record = OTPVerification.query.filter_by(user_id=current_user.id, otp=user_input, used=False).first()
            if otp_record:
                if otp_record.expires_at < datetime.utcnow():
                    flash("OTP has expired. Please request a new one.", "danger")
                    return redirect(url_for('send_otp'))
                else:
                    otp_record.used = True
                    current_user.verified = True
                    db.session.commit()
                    flash("Your phone number has been verified successfully!", "success")
                    return redirect(url_for('home'))
            else:
                flash("Invalid OTP. Please try again.", "danger")
                return redirect(url_for('verify_otp'))
        return render_template('verify_otp.html', email=current_user.email)
    
    @app.route('/resend-otp', methods=['POST'])
    @login_required
    def resend_otp():
        return redirect(url_for('send_otp'))
    
    # End of route registration

# ---------------------------- #
#      Error Handlers
# ---------------------------- #

def register_error_handlers(app):
    @app.errorhandler(403)
    def forbidden(e):
        return render_template('403.html'), 403

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        return render_template('500.html'), 500

# ---------------------------- #
#      CLI Commands
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
#      Login Manager Setup
# ---------------------------- #

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ---------------------------- #
#      Expose the WSGI Application
# ---------------------------- #

app = create_app()

if __name__ == "__main__":
    app.run()

