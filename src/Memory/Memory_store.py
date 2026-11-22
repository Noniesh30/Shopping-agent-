import json
import hashlib
import re
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import HTTPException
from pydantic import BaseModel
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
USER_DATA_PATH = PROJECT_ROOT / "Users" / "shop_users.json"
MEMORY_DIRECTORY = PROJECT_ROOT / "User_Memory"

# Request model
class DataRequest(BaseModel):
    data: dict[str, Any]
    user_prompt: str
    user_id: str


class EmailRequest(BaseModel):
    email: str


class ProductMemoryRequest(BaseModel):
    user_id: str
    product: dict[str, Any]


def write_json_atomically(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        suffix=".tmp",
        delete=False,
    ) as temporary_file:
        json.dump(data, temporary_file, indent=2)
        temporary_path = Path(temporary_file.name)
    temporary_path.replace(path)


def load_user_data() -> dict[str, Any]:
    if not USER_DATA_PATH.exists():
        return {"users": []}
    user_data = json.loads(USER_DATA_PATH.read_text(encoding="utf-8"))
    if not isinstance(user_data, dict) or not isinstance(user_data.get("users"), list):
        raise ValueError("The user JSON file has an invalid structure.")
    if any(not isinstance(user, dict) or not isinstance(user.get("email"), str) for user in user_data["users"]):
        raise ValueError("The user JSON file contains an invalid user entry.")
    return user_data


def user_memory_path(user_id: str) -> Path:
    username = user_id.partition("@")[0]
    safe_username = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", username).rstrip(" .")
    if not safe_username:
        raise ValueError("The user ID does not contain a valid filename.")
    if safe_username.upper() in {
        "CON", "PRN", "AUX", "NUL",
        *(f"COM{number}" for number in range(1, 10)),
        *(f"LPT{number}" for number in range(1, 10)),
    }:
        safe_username = f"_{safe_username}"
    return MEMORY_DIRECTORY / f"{safe_username}.json"


def migrate_legacy_clicks(
    user_id: str,
    memory: dict[str, Any],
    preference_records: list[dict[str, Any]],
) -> None:
    prompt_records = memory.get("prompt_memory", [])
    click_records = memory.get("click_memory", [])
    if not isinstance(prompt_records, list) or any(
        not isinstance(record, dict) for record in prompt_records
    ):
        raise ValueError("The legacy prompt_memory data has an invalid structure.")
    if not isinstance(click_records, list) or any(
        not isinstance(record, dict) for record in click_records
    ):
        raise ValueError("The legacy click_memory data has an invalid structure.")

    prompts_by_category = {}
    name_counts: dict[str, int] = {}
    for record in prompt_records:
        name = record.get("name")
        if not isinstance(name, str):
            continue
        normalized_name = name.strip().lower()
        name_counts[normalized_name] = name_counts.get(normalized_name, 0) + 1
        prompts_by_category[f"{normalized_name}-{name_counts[normalized_name]}"] = record

    for click_record in click_records:
        linked_memory_id = click_record.get("preference_memory_id")
        if any(
            record.get("memory_id") == linked_memory_id
            and record.get("source_type") == "agent_inferred"
            for record in preference_records
        ):
            continue

        product = click_record.get("product", {})
        category = product.get("category") if isinstance(product, dict) else None
        prompt_record = prompts_by_category.get(category)
        if prompt_record is None:
            continue

        memory_fields = {
            key: prompt_record.get(key)
            for key in (
                "name",
                "keywords",
                "preferences",
                "budget",
                "min_rating",
                "min_reviews",
                "category_id",
            )
        }
        created_at = click_record.get("created_at") or datetime.now(timezone.utc).isoformat()
        preference_records.append({
            "user_id": user_id,
            "memory_id": max(
                (int(record.get("memory_id", 0)) for record in preference_records),
                default=0,
            ) + 1,
            **memory_fields,
            "source_type": "agent_inferred",
            "created_at": created_at,
            "last_updated_at": created_at,
            "use_freq": 0,
            "hash_value": hashlib.sha256(
                json.dumps(
                    memory_fields,
                    sort_keys=True,
                    ensure_ascii=False,
                ).encode("utf-8")
            ).hexdigest(),
        })


def load_user_memory(user_id: str) -> dict[str, Any]:
    path = user_memory_path(user_id)

    if path.exists():
        memory = json.loads(path.read_text(encoding="utf-8"))

        # Handle legacy list format
        if isinstance(memory, list):
            memory = {
                "user_id": user_id,
                "preference_memory": memory,
            }

        if not isinstance(memory, dict):
            raise ValueError("The user memory file has an invalid structure.")

    else:
        memory = {}

    # Initialize top-level structure
    records = memory.get("preference_memory", [])
    if not isinstance(records, list) or any(not isinstance(record, dict) for record in records):
        raise ValueError("The preference_memory data has an invalid structure.")
    migrate_legacy_clicks(user_id, memory, records)
    for record in records:
        if record.get("source_type") == "agent_inferred":
            record.setdefault("bought", False)

    unique_records = []
    inferred_by_product_id = {}
    for record in records:
        product_id = record.get("product_id")
        if record.get("source_type") != "agent_inferred" or not product_id:
            unique_records.append(record)
            continue

        existing = inferred_by_product_id.get(product_id)
        if existing is None:
            inferred_by_product_id[product_id] = record
            unique_records.append(record)
            continue

        existing["bought"] = bool(existing.get("bought")) or bool(record.get("bought"))
        for field in ("product_name", "product_details", "last_updated_at"):
            if field in record:
                existing[field] = record[field]

    return {
        "user_id": user_id,
        "preference_memory": unique_records,
    }


def click(user_memory: dict[str, Any]) -> dict[str, Any]:
    return user_memory


def buy(user_memory: dict[str, Any]) -> dict[str, Any]:
    return user_memory





def migrate_legacy_memory(user: dict[str, Any], user_id: str) -> None:
    legacy_id = user.get("user_id")
    memory_path = user_memory_path(user_id)
    memory = load_user_memory(user_id)
    paths_to_remove = []

    if isinstance(legacy_id, int):
        legacy_path = MEMORY_DIRECTORY / f"user_{legacy_id}.json"
        if legacy_path.exists() and legacy_path != memory_path:
            legacy_records = json.loads(legacy_path.read_text(encoding="utf-8"))
            if not isinstance(legacy_records, list) or any(
                not isinstance(record, dict) for record in legacy_records
            ):
                raise ValueError("The legacy user memory file has an invalid structure.")
            memory["preference_memory"].extend(legacy_records)
            for memory_id, record in enumerate(memory["preference_memory"], start=1):
                record["user_id"] = user_id
                record["memory_id"] = memory_id
            paths_to_remove.append(legacy_path)

    write_json_atomically(memory_path, memory)
    for path in paths_to_remove:
        path.unlink()
    user["user_id"] = user_id


def get_registered_user(user_data: dict[str, Any], user_id: str) -> dict[str, Any] | None:
    return next(
        (
            user for user in user_data["users"]
            if user.get("email", "").strip().lower() == user_id
        ),
        None,
    )