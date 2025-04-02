# 🛍️ Wazobia List - Free Nigerian Classifieds

[![Live Demo](https://img.shields.io/badge/demo-live-brightgreen)](https://wazobia-list-service.onrender.com)
[![Built with Flask](https://img.shields.io/badge/Powered%20by-Flask-blue)](https://flask.palletsprojects.com/)

A Craigslist-inspired marketplace focused on Nigeria, built with modern web technologies.

## 🛠️ Tech Stack

- **Backend:** Python/Flask
- **Database:** SQLite (Development), PostgreSQL (Production)
- **Frontend:** Bootstrap 5
- **Hosting:** Render.com
- **CI/CD:** GitHub + Render

## 🚀 Getting Started

### Prerequisites
- Python 3.8+
- pip
- Git

### 🔧 Installation

1. **Clone the repository**
		- git clone https://github.com/yourusername/wazobia-list.git
		- cd wazobia-list
2. **Set up virtual environment**
		- python -m venv venv
		 # Linux/Mac
		- source venv/bin/activate
			# Windows
			 .\venv\Scripts\activate
3. **Install dependencies**
	 pip install -r requirements.txt

4. **Run the development server**
	flask run
	Visit `http://localhost:5000` in your browser

## 🌐 Deployment

1. Push changes to your GitHub repository
    
2. Connect repository to [Render.com](https://render.com/)
    
3. Set environment variables:
		-- FLASK_ENV=production
		-- SECRET_KEY=your_generated_secret_key

4. Render will automatically:
    
    - Run database migrations (`flask db upgrade`)
        
    - Start production server with Gunicorn
        

## 🌱 Database Seeding

Default categories are automatically seeded on first launch if none exist:

- 📱 Electronics
    
- 🛋️ Furniture
    
- 🚗 Vehicles
    
- 👗 Fashion
    

The seeding process is handled by `@app.before_first_request` handler.

## 📄 License

This project is open-source. (Add your license here)

---

**Happy trading!** 🇳🇬 💼