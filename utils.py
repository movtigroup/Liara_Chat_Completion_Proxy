import json
import hashlib
from functools import lru_cache

@lru_cache(maxsize=128)
def get_headers(api_key: str):
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

def generate_cache_key(request_data: dict) -> str:
    """ساخت کلید منحصر به فرد برای کش"""
    return hashlib.sha256(
        json.dumps(request_data, sort_keys=True).encode()
    ).hexdigest()
