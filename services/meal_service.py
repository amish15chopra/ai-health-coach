import os
import uuid
import json
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException, UploadFile
from models import Meal
from schemas import AdviceResponse, MealRead, NutritionInfo
from services.user_service import get_user
from openai import OpenAI
import base64
from datetime import date

# Set your OpenAI API key
openai_api_key = os.getenv("OPENAI_API_KEY")

# Initialize OpenAI Responses client
client = OpenAI(api_key=openai_api_key)

def detect_food_items(image_path: str) -> List[str]:
    """
    Uses OpenAI GPT-4o with Structured Outputs to detect food items as a JSON array.
    """
    with open(image_path, "rb") as img_file:
        image_bytes = img_file.read()
    image_b64 = base64.b64encode(image_bytes).decode()
    schema = {
        "type": "object",
        "properties": {
            "food_items": {
                "type": "array",
                "items": {"type": "string"}
            }
        },
        "required": ["food_items"],
        "additionalProperties": False,
    }
    response = client.responses.create(
        model="gpt-4o",
        input=[
            {"role": "user", "content": [
                {"type": "input_text", "text": "List all food items you see in this photo. Return strictly a JSON object with a single key \"food_items\" mapping to an array of strings. Do not include any other keys."},
                {"type": "input_image", "image_url": f"data:image/jpeg;base64,{image_b64}"}
            ]}
        ],
        text={"format": {"type": "json_schema", "name": "food_items", "schema": schema, "strict": True}},
        max_output_tokens=200,
    )
    content = response.output_text
    try:
        obj = json.loads(content)
        return obj["food_items"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse food items: {e}")


def estimate_nutrition(food_items: List[str]) -> Dict[str, Any]:
    """
    Uses OpenAI GPT-4o with Structured Outputs (JSON Schema) to estimate nutrition.
    """
    # Prepare JSON schema
    schema = {
        "type": "object",
        "properties": {
            "calories": {"type": "integer"},
            "protein": {"type": "integer"},
            "carbs": {"type": "integer"},
            "fat": {"type": "integer"},
        },
        "required": ["calories", "protein", "carbs", "fat"],
        "additionalProperties": False,
    }
    response = client.responses.create(
        model="gpt-4o",
        input=[
            {"role": "system", "content": "You are a knowledgeable nutrition assistant."},
            {"role": "user", "content": f"Estimate total nutrition for these items: {food_items}."}
        ],
        text={"format": {"type": "json_schema", "name": "nutrition_info", "schema": schema, "strict": True}},
        temperature=0.2,
    )
    content = response.output_text
    try:
        nutrition = NutritionInfo.model_validate_json(content)
        return nutrition.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Nutrition JSON validation failed: {e}")


async def analyze_meal(db: Session, user_id: int, file: UploadFile) -> Dict[str, Any]:
    # Validate user exists
    user = get_user(db, user_id)

    # Save uploaded image
    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)
    ext = os.path.splitext(file.filename)[1]
    filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(upload_dir, filename)
    contents = await file.read()
    with open(file_path, "wb") as f:
        f.write(contents)

    # Detect food items and estimate nutrition
    items = detect_food_items(file_path)
    food_items = {"items": items}
    nutrition_info = estimate_nutrition(items)

    # Fetch today's meal history and prepare for next meal advice
    all_history = get_meal_history(db, user_id)
    today = date.today()
    todays_meals = []
    for m in all_history:
        if m.timestamp.date() == today:
            todays_meals.append({
                "timestamp": m.timestamp.isoformat(),
                "food_items": m.food_items,
                "nutrition_info": m.nutrition_info,
                "feedback": m.feedback.dict() if hasattr(m.feedback, "dict") else m.feedback
            })

    # Prepare prompt for AI
    user_profile = user.dict()
    prompt = (
        f"User profile: {json.dumps(user_profile)}."
        f"Today's meals: {json.dumps(todays_meals)}."
        f"Current meal: {json.dumps(food_items)} with nutrition {json.dumps(nutrition_info)}."
        "Based on today's meals, provide dietary advice for the next meal in a friendly, coach-like tone."
        "Speak like a personal health coach. Respond strictly in JSON with keys: advice, reason, next_meal."
    )
    # Generate advice using Structured Outputs (JSON Schema)
    advice_schema = {
        "type": "object",
        "properties": {
            "advice": {"type": "string"},
            "reason": {"type": "string"},
            "next_meal": {"type": "string"},
        },
        "required": ["advice", "reason", "next_meal"],
        "additionalProperties": False,
    }
    response = client.responses.create(
        model="gpt-4o",
        input=[
            {"role": "system", "content": "You are a friendly personal health coach. Speak with empathy and encouragement."},
            {"role": "user", "content": prompt}
        ],
        text={"format": {"type": "json_schema", "name": "advice_response", "schema": advice_schema, "strict": True}},
        temperature=0.7,
    )
    content = response.output_text
    try:
        feedback = AdviceResponse.model_validate_json(content).model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Advice JSON validation failed: {e}")

    # Persist meal record
    meal = Meal(
        user_id=user_id,
        image_path=file_path,
        food_items=food_items,
        nutrition_info=nutrition_info,
        feedback=feedback,
    )
    db.add(meal)
    db.commit()
    db.refresh(meal)
    return {
        "id": meal.id,
        "user_id": meal.user_id,
        "timestamp": meal.timestamp.isoformat(),
        "image_path": meal.image_path,
        "food_items": meal.food_items,
        "nutrition_info": meal.nutrition_info,
        "feedback": meal.feedback
    }


def get_meal_history(db: Session, user_id: int) -> List[MealRead]:
    meals = db.query(Meal).filter(Meal.user_id == user_id).order_by(Meal.timestamp.desc()).all()
    return [MealRead.from_orm(m) for m in meals]
