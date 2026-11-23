import json
import hmac
from src.Values.config import SECRET_KEY

def calculate_hash(record):
    record_data = record.copy()
    record_data.pop("hash_value", None)
    record_data.pop("assessed_values", None)
    record_string = json.dumps(
        record_data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False
    )
    return hmac.new(
        SECRET_KEY,
        record_string.encode("utf-8"),
        digestmod="sha256"
    ).hexdigest()

