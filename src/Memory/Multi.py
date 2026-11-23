import threading
import json
import hashlib
import re
import tempfile
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import HTTPException
from pydantic import BaseModel
from typing import Any


from src.Memory.Memory_store import load_user_data,get_registered_user,load_user_memory,write_json_atomically
from src.Memory.Memory_store import user_memory_path

user_data_lock = threading.Lock()

def append_preference_memory_record(
    memory: dict[str, Any],
    user_id: str,
    item: dict[str, Any],
    source_type: str,
    use_freq: int,
    product: dict[str, Any] | None = None,
    bought: bool | None = None,
    action: Callable[[dict[str, Any]], dict[str, Any]]|None = None,
) -> dict[str, Any]:
    
    records = memory["preference_memory"]
    memory_fields = requirement_memory_fields(item)
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "user_id": user_id,
        "memory_id": max(
            (int(existing.get("memory_id", 0)) for existing in records),
            default=0,
        ) + 1,
        **memory_fields,
        "source_type": source_type,
    }
    if product is not None:
        record.update({
            "Category_id":product.get("category_id"),
            "Category Name":product.get("category_name"),
            "product_id": product.get("asin") or product.get("id"),
            "product_name": product.get("title") or product.get("name"),
            "product_details": product,
        })

    if bought is not None:
        record["bought"] = bought

    if action is not None:
        record=action(record)

    

    record.update({
        "created_at": now,
        "last_updated_at": now,
        "use_freq": use_freq,
        "hash_value": hashlib.sha256(
            json.dumps(
                memory_fields,
                sort_keys=True,
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest(),
    })
    records.append(record)
    return record

def requirement_memory_fields(item: dict[str, Any]) -> dict[str, Any]:
    attributes = item.get("attributes", {})
    if not isinstance(attributes, dict):
        attributes = {}

    preference_fields = ("color", "size", "target_user", "material", "brand", "use_case")
    preferences: dict[str, Any] = {key: "" for key in preference_fields}
    preferences["others"] = []

    def preference_value(value: Any) -> str:
        if isinstance(value, list):
            return ", ".join(str(entry) for entry in value if entry is not None)
        return str(value) if value is not None else ""

    raw_preferences = item.get("preferences")
    if isinstance(raw_preferences, dict):
        for key, value in raw_preferences.items():
            if key in preference_fields:
                normalized_value = preference_value(value)
                if normalized_value:
                    preferences[key] = normalized_value
            elif key == "others" and isinstance(value, list):
                preferences["others"].extend(value)
            elif value:
                preferences["others"].append(f"{key}: {preference_value(value)}")
    elif isinstance(raw_preferences, list):
        preferences["others"].extend(raw_preferences)

    for key, value in attributes.items():
        if key in preference_fields:
            normalized_value = preference_value(value)
            if normalized_value:
                preferences[key] = normalized_value
        elif key == "others" and isinstance(value, list):
            preferences["others"].extend(value)
        elif value:
            preferences["others"].append(f"{key}: {preference_value(value)}")

    return {
        "name": item.get("name", ""),
        "keywords": item.get("keywords", []),
        "preferences": preferences,
        "budget": item.get("budget"),
        "min_rating": item.get("min_rating"),
        "min_reviews": item.get("min_reviews"),
        "category_id": item.get("category_id", []),
    }


def requirements_by_search_category(
    requirements: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    items = requirements.get("items")
    if not isinstance(items, list):
        raise ValueError("Extracted requirements must contain an items list.")

    category_requirements = {}
    name_counts: dict[str, int] = {}
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise ValueError("An extracted requirement has an invalid name.")
        name = item["name"].strip().lower()
        name_counts[name] = name_counts.get(name, 0) + 1
        category_requirements[f"{name}-{name_counts[name]}"] = item
    return category_requirements



def inferred_item_from_product(product: dict[str, Any]) -> dict[str, Any]:
    category = product.get("category")
    title = product.get("title")
    category_name = re.sub(r"-\d+$", "", category).replace("-", " ") if isinstance(category, str) else ""
    name = category_name or (title.strip() if isinstance(title, str) else "")
    return {
        "name": name,
        "keywords": re.findall(r"[a-z0-9]+", name.lower()),
        "preferences": {},
        "budget": None,
        "min_rating": None,
        "min_reviews": None,
        "category_id": [],
    }

def save_user_memory(user_id: str, requirements: dict[str, Any]) -> list[dict[str, Any]]:
    items = requirements.get("items")
    if not isinstance(items, list):
        raise ValueError("Extracted requirements must contain an items list.")

    memory_path = user_memory_path(user_id)
    present_promt_records = []

    with user_data_lock:
        try:
            user_data = load_user_data()
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(status_code=500, detail="Could not read registered users.") from exc

        if get_registered_user(user_data, user_id) is None:
            raise HTTPException(status_code=404, detail="User not found.")

        memory = load_user_memory(user_id)
        records = memory["preference_memory"]
        now = datetime.now(timezone.utc).isoformat()

        for item in items:
            if not isinstance(item, dict):
                raise ValueError("An extracted requirement is invalid.")

            memory_data = requirement_memory_fields(item)
            fingerprint = hashlib.sha256(
                json.dumps(memory_data, sort_keys=True, ensure_ascii=False).encode("utf-8")
            ).hexdigest()

            existing = next(
                (record for record in records if record.get("hash_value") == fingerprint),
                None,
            )

            if existing is not None:
                existing["last_updated_at"] = now
                existing["use_freq"] = int(existing.get("use_freq", 1)) + 1
                present_promt_records.append(existing)
                continue

            record = append_preference_memory_record(
                memory, user_id, item,
                source_type="user_prompt",
                use_freq=1,
                action=None
            )
            record["created_at"] = now
            record["last_updated_at"] = now
            record["hash_value"] = fingerprint
            present_promt_records.append(record)

        write_json_atomically(memory_path, memory)

    return present_promt_records


