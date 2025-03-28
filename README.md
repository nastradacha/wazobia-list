
# Wazobia List - Free Nigerian Classifieds

[![Live Demo](https://img.shields.io/badge/demo-live-brightgreen)](https://wazobia-list-service.onrender.com)

A Craigslist-inspired marketplace focused on Nigeria, built with:
- Python/Flask backend
- SQLite/PostgreSQL database
- Bootstrap 5 frontend
- Deployed on Render.com

## 🔧 Setup
1. Clone repo:

```bash
git clone https://github.com/yourusername/wazobia-list.git
cd wazobia-list
```

2. Create virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate    # Windows
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Run locally:

```bash
flask run
```

## 🚀 Deployment
- Push to GitHub
- Connect repo to Render.com
- Set environment variables in Render:

```
FLASK_ENV=production
SECRET_KEY=your_generated_key
```
