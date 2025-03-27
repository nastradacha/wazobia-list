from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'  # SQLite database file
app.config['SECRET_KEY'] = 'your-secret-key-here'  # Required for Flask-Login later
db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)  # Will hash later

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)

class Listing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    price = db.Column(db.String(20))
    description = db.Column(db.Text)
    location = db.Column(db.String(50), default='Lagos')  # Lagos-focused
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))

# Initialize the database
with app.app_context():
    db.create_all()

@app.route("/")
def home():
    listings = Listing.query.all()
    return render_template("index.html", listings=listings)

if __name__ == "__main__":
    app.run(debug=True)
