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
#        App Configuration      #
# ---------------------------- #

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.getenv('SECRET_KEY', 'dev-secret-key-22aa0cd08a839a23a061c102ce4bd644'),
    SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URL', '').replace('postgres://', 'postgresql://', 1),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=os.getenv('FLASK_ENV') == 'production',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=2)
)

# ---------------------------- #
#        Extensions Setup       #
# ---------------------------- #

db = SQLAlchemy(app)
# with app.app_context():
#     try:
#         db.create_all()
#         Category.__table__.create(db.engine, checkfirst=True)
#     except Exception as e:
#         logger.error(f"Table creation error: {str(e)}")
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# ---------------------------- #
#         Logging Setup         #
# ---------------------------- #

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
#       Helper Functions        #
# ---------------------------- #

def generate_otp() -> str:
    """Generate a 6-digit numeric OTP"""
    return str(random.randint(100000, 999999))

def send_otp_via_email(email: str, otp: str) -> bool:
    """Mock email sending function (replace with real implementation in production)"""
    try:
        logger.info(f"OTP for {email}: {otp}")
        # TODO: Implement real email sending here
        return True
    except Exception as e:
        logger.error(f"Email send failed: {str(e)}")
        return False

def cleanup_expired_otps():
    """Remove expired OTP entries from database"""
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
#      Login Manager Setup      #
# ---------------------------- #

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ---------------------------- #
#        Error Handlers         #
# ---------------------------- #

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
#        Auth Routes            #
# ---------------------------- #

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Handle user registration with OTP verification"""
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        try:
            form_data = {
                'username': request.form['username'].strip(),
                'email': request.form['email'].lower().strip(),
                'phone': request.form['phone'].strip(),
                'password': request.form['password']
            }
            
            if User.query.filter(or_(
                User.username == form_data['username'],
                User.email == form_data['email'],
                User.phone == form_data['phone']
            )).first():
                flash('Username, email or phone already exists', 'danger')
                return redirect(url_for('register'))
            
            new_user = User(**form_data)
            new_user.set_password(form_data['password'])
            
            db.session.add(new_user)
            db.session.commit()
            
            # Generate and store OTP
            otp = generate_otp()
            db.session.add(OTPVerification(
                user_id=new_user.id,
                otp=otp,
                expires_at=datetime.utcnow() + timedelta(minutes=10)
            ))
            db.session.commit()
            
            if not send_otp_via_email(new_user.email, otp):
                logger.error(f"Failed to send OTP to {new_user.email}")
                flash('Error sending verification code', 'danger')
                return redirect(url_for('register'))
            
            session.update({
                'verify_user_id': new_user.id,
                'verify_email': new_user.email
            })
            return redirect(url_for('verify_otp'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Registration error: {str(e)}")
            flash('Registration failed. Please try again.', 'danger')
    
    return render_template('register.html')

@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    """Handle OTP verification process"""
    verification_data = {
        'user_id': session.get('verify_user_id'),
        'email': session.get('verify_email')
    }
    
    if not all(verification_data.values()):
        flash('Verification session expired', 'danger')
        return redirect(url_for('register'))
    
    user = User.query.filter_by(
        id=verification_data['user_id'],
        email=verification_data['email']
    ).first()
    
    if not user:
        flash('Invalid verification session', 'danger')
        return redirect(url_for('register'))
    
    if request.method == 'POST':
        cleanup_expired_otps()  # Cleanup before verification
        
        otp = request.form.get('otp', '').strip()
        verification = OTPVerification.query.filter(
            OTPVerification.user_id == user.id,
            OTPVerification.used == False,
            OTPVerification.expires_at >= datetime.utcnow()
        ).order_by(OTPVerification.created_at.desc()).first()
        
        if verification and verification.otp == otp:
            verification.used = True
            user.verified = True
            db.session.commit()
            
            login_user(user)
            session.pop('verify_user_id', None)
            session.pop('verify_email', None)
            
            flash('Email verification successful!', 'success')
            return redirect(url_for('home'))
        
        flash('Invalid or expired verification code', 'danger')
    
    return render_template('verify_otp.html', email=user.email)

@app.route('/resend-otp', methods=['POST'])
@limiter.limit("3 per hour")
def resend_otp():
    """Handle OTP resend requests"""
    verification_data = {
        'user_id': session.get('verify_user_id'),
        'email': session.get('verify_email')
    }
    
    if not all(verification_data.values()):
        flash('Session expired', 'danger')
        return redirect(url_for('register'))
    
    user = User.query.filter_by(
        id=verification_data['user_id'],
        email=verification_data['email']
    ).first()
    
    if not user:
        flash('Invalid session', 'danger')
        return redirect(url_for('register'))
    
    # Invalidate existing OTPs
    OTPVerification.query.filter_by(user_id=user.id).update({'used': True})
    
    # Generate new OTP
    otp = generate_otp()
    db.session.add(OTPVerification(
        user_id=user.id,
        otp=otp,
        expires_at=datetime.utcnow() + timedelta(minutes=10)
    ))
    db.session.commit()
    
    if send_otp_via_email(user.email, otp):
        flash('New verification code sent', 'success')
    else:
        flash('Failed to resend code', 'danger')
    
    return redirect(url_for('verify_otp'))


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
        
        return render_template("index.html", listings=listings.all(),
                               categories=categories, selected_category=category_id,
                               search_query=search_query)
    except Exception as e:
        app.logger.error(f"Homepage error: {str(e)}")
        flash("Error loading listings. Please try again later.", "danger")
        return redirect(url_for('home'))

@app.route("/post", methods=["POST"])
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

        new_ad = Listing(title=request.form["title"],
                         price=request.form["price"],
                         location=request.form.get("location", "Lagos"),
                         description=request.form["description"],
                         phone=request.form["phone"],
                         category_id=category_id,
                         user_id=current_user.id)
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

# ... (Keep other routes unchanged from previous version with improved error handling)

# ---------------------------- #
#      App Initialization       #
# ---------------------------- #

@app.cli.command("seed-categories")
def seed_categories():
    """Seed default categories"""
    default_categories = ['Electronics', 'Furniture', 'Vehicles', 'Fashion']
    try:
        for name in default_categories:
            if not Category.query.filter_by(name=name).first():
                db.session.add(Category(name=name))
        db.session.commit()
        logger.info("Categories seeded successfully")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Category seeding failed: {str(e)}")

if __name__ == "__main__":
    app.run()