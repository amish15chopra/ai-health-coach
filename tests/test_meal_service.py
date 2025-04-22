import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import json
import pytest
from fastapi import HTTPException
from services.meal_service import detect_food_items, estimate_nutrition


def test_detect_food_items_success(monkeypatch, tmp_path):
    # Create a dummy image file
    img_file = tmp_path / "dummy.jpg"
    img_file.write_bytes(b"\xff\xd8\xff\xd9")  # minimal JPEG file bytes

    expected_items = ["apple", "banana"]
    # Mock call_openai to return a JSON object with food_items
    def fake_call_openai(messages, schema, name, temperature=0.0, max_output_tokens=None):
        return json.dumps({"food_items": expected_items})
    monkeypatch.setattr("services.meal_service.call_openai", fake_call_openai)

    result = detect_food_items(str(img_file))
    assert result == expected_items


def test_detect_food_items_invalid_json(monkeypatch, tmp_path):
    img_file = tmp_path / "dummy.jpg"
    img_file.write_bytes(b"data")

    # Return invalid JSON
    monkeypatch.setattr("services.meal_service.call_openai", lambda m, s, n, temperature=0.0, max_output_tokens=None: "not a json")
    with pytest.raises(HTTPException) as exc:
        detect_food_items(str(img_file))
    assert "Failed to parse food items" in str(exc.value.detail)


def test_estimate_nutrition_success(monkeypatch):
    items = ["apple", "banana"]
    expected_nutrition = {"calories": 150, "protein": 3, "carbs": 35, "fat": 1}

    # Mock call_openai to return valid JSON
    def fake_call_openai(messages, schema, name, temperature=0.0, max_output_tokens=None):
        return json.dumps(expected_nutrition)
    monkeypatch.setattr("services.meal_service.call_openai", fake_call_openai)

    result = estimate_nutrition(items)
    assert result == expected_nutrition


def test_estimate_nutrition_invalid_json(monkeypatch):
    items = ["apple"]
    monkeypatch.setattr("services.meal_service.call_openai", lambda m, s, n, temperature=0.0, max_output_tokens=None: "{invalid-json}")
    with pytest.raises(HTTPException) as exc:
        estimate_nutrition(items)
    assert "Nutrition JSON validation failed" in str(exc.value.detail)
