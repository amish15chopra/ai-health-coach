# Turtle Meal Analyzer Backend

This is an MVP backend for **Turtle**, an AI health agent that helps busy professionals make healthy food choices. 

## Tech Stack
- **FastAPI** (Python) for the REST API
- **PostgreSQL** for data storage (SQLAlchemy ORM)
- **OpenAI API** (GPT-4 + GPT-4 Vision placeholder) for food detection and dietary feedback
- **Local file storage** for uploaded images

## Setup
1. Clone the repo:
   ```bash
   git clone <repo_url>
   cd health-coach
   ```
2. Create and activate a virtualenv (optional but recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure environment variables:
   - Copy `.env` and update values:
     ```env
     DATABASE_URL=postgresql://user:password@localhost:5432/turtle_db
     OPENAI_API_KEY=your_openai_key_here
     ```
5. Ensure PostgreSQL is running and `turtle_db` exists.

## Running the Server
```bash
uvicorn main:app --reload
```

## API Endpoints
- `POST /user` — Create or update a user profile
- `GET /user/{user_id}` — Fetch user profile
- `POST /analyze_meal` — Upload a meal photo (`multipart/form-data` with `user_id` and `file`) and get AI analysis
- `GET /meal_history/{user_id}` — Retrieve past meals and feedback
- `GET /` — Simple HTML/JS frontend for testing image uploads

## File Structure
```
health-coach/
├── main.py           # FastAPI app
├── models.py         # SQLAlchemy models
├── schemas.py        # Pydantic schemas
├── services/         # Business logic modules
│   ├── user_service.py
│   └── meal_service.py
├── frontend/         # Simple HTML+JS UI
│   └── index.html
├── uploads/          # Stored meal photos (created at runtime)
├── requirements.txt
├── .env
└── README.md
```

## Notes
- `detect_food_items` is a placeholder. Integrate GPT-4 Vision or BLIP-2 for real food detection.
- Nutrition estimation is mocked.
- Feedback is generated via GPT-4; responses must be valid JSON.

Feel free to extend or refine the detection and nutrition logic. Let me know if you need any further enhancements!
