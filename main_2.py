
import json
import hashlib
import re
import tempfile
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import HTTPException
from pydantic import BaseModel
from typing import Any

app = FastAPI(title="Cross-Platform API")

#Search Module
from src.Search.Data_ingest import data_ingest 
from src.Search.search import Searching
from src.LLM.template import extract_requirements
import pandas as pd

#Memory Module 
from src.Memory.Memory_store import load_user_data,get_registered_user,load_user_memory,write_json_atomically
from src.Memory.Memory_store import user_memory_path,EmailRequest,migrate_legacy_memory,DataRequest,ProductMemoryRequest
from src.Memory.Memory_store import USER_DATA_PATH,MEMORY_DIRECTORY
from src.Memory.Memory_store import buy,click

print("Startup Completed")
products,categories=data_ingest()
obj=Searching(products,categories)  

user_data_lock = threading.Lock()

def get_product_solutions(prompt):
    main_template=extract_requirements(prompt)
    print(main_template)
    solutions=obj.finding_products(main_template)
    return solutions


# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
    "http://localhost:8501",
    "http://127.0.0.1:8501"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Temporary storage for received data
data_store = {}


def append_preference_memory_record(
    memory: dict[str, Any],
    user_id: str,
    item: dict[str, Any],
    source_type: str,
    use_freq: int,
    product: dict[str, Any] | None = None,
    bought: bool | None = None,
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
            "product_id": product.get("asin") or product.get("id"),
            "product_name": product.get("title") or product.get("name"),
            "product_details": product,
        })
    if bought is not None:
        record["bought"] = bought
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


def pass_through_user_memory(
    user_id: str,
    memory_type: str,
    product: dict[str, Any],
    action: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    with user_data_lock:
        try:
            user_data = load_user_data()
            if get_registered_user(user_data, user_id) is None:
                raise HTTPException(status_code=404, detail="User not found.")
            memory_path = user_memory_path(user_id)
            memory = load_user_memory(user_id)

            if memory_type == "click":
                category = product.get("category")
                product_id = product.get("asin") or product.get("id")
                product_name = product.get("title") or product.get("name")
                inferred_record = next(
                    (
                        record for record in reversed(memory["preference_memory"])
                        if record.get("source_type") == "agent_inferred"
                        and (
                            (product_id and record.get("product_id") == product_id)
                            or (
                                not product_id
                                and product_name
                                and record.get("product_name") == product_name
                            )
                        )
                    ),
                    None,
                )
                item = data_store.get(user_id, {}).get(
                    "requirements_by_category",
                    {},
                ).get(category)
                if item is None:
                    item = inferred_item_from_product(product)
                if inferred_record is None:
                    append_preference_memory_record(
                        memory,
                        user_id,
                        item,
                        source_type="agent_inferred",
                        use_freq=0,
                        product=product,
                        bought=False,
                    )
                else:
                    inferred_record["product_id"] = product_id
                    inferred_record["product_name"] = product_name
                    inferred_record["product_details"] = product
                    inferred_record["last_updated_at"] = datetime.now(timezone.utc).isoformat()
            elif memory_type == "buy":
                product_id = product.get("asin") or product.get("id")
                category = product.get("category")
                category_name = (
                    re.sub(r"-\d+$", "", category).replace("-", " ").strip().lower()
                    if isinstance(category, str)
                    else ""
                )
                inferred_record = next(
                    (
                        record for record in reversed(memory["preference_memory"])
                        if record.get("source_type") == "agent_inferred"
                        and (
                            record.get("product_id") == product_id
                            or record.get("product_name") == (
                                product.get("title") or product.get("name")
                            )
                            or (
                                not record.get("product_id")
                                and category_name
                                and str(record.get("name", "")).strip().lower()
                                == category_name
                            )
                        )
                    ),
                    None,
                )
                if inferred_record is None:
                    item = data_store.get(user_id, {}).get(
                        "requirements_by_category",
                        {},
                    ).get(category)
                    if item is None:
                        item = inferred_item_from_product(product)
                    inferred_record = append_preference_memory_record(
                        memory,
                        user_id,
                        item,
                        source_type="agent_inferred",
                        use_freq=0,
                        product=product,
                        bought=True,
                    )
                else:
                    inferred_record["bought"] = True
                    inferred_record["product_id"] = product_id
                    inferred_record["product_name"] = (
                        product.get("title") or product.get("name")
                    )
                    inferred_record["product_details"] = product
                    inferred_record["last_updated_at"] = datetime.now(timezone.utc).isoformat()

            updated_memory = action(memory)
            if not isinstance(updated_memory, dict):
                raise ValueError("The memory action must return a JSON object.")
            write_json_atomically(memory_path, updated_memory)
            return updated_memory
        except HTTPException:
            raise
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=500,
                detail="Could not process user memory action.",
            ) from exc


@app.post("/users")
def store_user_email(request: EmailRequest):
    email = request.email.strip().lower()
    if len(email) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(status_code=422, detail="Enter a valid email address.")

    with user_data_lock:
        try:
            user_data = load_user_data()
            users = user_data["users"]

            user = next((entry for entry in users if entry["email"].lower() == email), None)
            already_registered = user is not None
            if user is None:
                user = {
                    "user_id": email,
                    "email": email,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                users.append(user)
            for entry in users:
                entry_email = entry["email"].strip().lower()
                migrate_legacy_memory(entry, entry_email)

            user_id = email
            write_json_atomically(USER_DATA_PATH, user_data)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(
                status_code=500,
                detail="Could not store the email address.",
            ) from exc

    return {
        "status": "success",
        "message": "Email stored successfully.",
        "already_registered": already_registered,
        "user_id": user_id,
    }


# Route 1: Receive data from the client
@app.post("/send")
def send_data(request: DataRequest):
    with user_data_lock:
        try:
            user_data = load_user_data()
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(status_code=500, detail="Could not read registered users.") from exc
        if get_registered_user(user_data, request.user_id) is None:
            raise HTTPException(status_code=404, detail="User not found.")

    data_store[request.user_id] = {"user_prompt": request.user_prompt}

    print("Received prompt:", request.user_prompt)
    return {
        "status": "success",
        "message": "Data received successfully",
    }


@app.post("/memory/click")
def record_product_click(request: ProductMemoryRequest):
    return pass_through_user_memory(
        request.user_id,
        "click",
        request.product,
        click,
    )


@app.post("/memory/buy")
def record_buy_click(request: ProductMemoryRequest):
    return pass_through_user_memory(
        request.user_id,
        "buy",
        request.product,
        buy,
    )


# Route 2: Send data to the client
@app.get("/recieve")
def receive_data(user_id: str):
    if user_id not in data_store:
        return {"data": []}
    prompt = data_store[user_id]["user_prompt"]
    try:
        requirements = extract_requirements(prompt)
        save_user_memory(user_id, requirements)
        data_store[user_id]["requirements_by_category"] = requirements_by_search_category(
            requirements
        )
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=500, detail="Could not save search memory.") from exc
    print(requirements)
    solutions = obj.finding_products(requirements)

    return {
        "data": solutions
    }


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


def save_user_memory(user_id: str, requirements: dict[str, Any]) -> None:
    items = requirements.get("items")
    if not isinstance(items, list):
        raise ValueError("Extracted requirements must contain an items list.")

    memory_path = user_memory_path(user_id)
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
                continue

            record = append_preference_memory_record(
                memory,
                user_id,
                item,
                source_type="user_prompt",
                use_freq=1,
            )
            record["created_at"] = now
            record["last_updated_at"] = now
            record["hash_value"] = fingerprint

        write_json_atomically(memory_path, memory)

# Health check
@app.get("/")
def home():
    return {"message": "API is running"}
