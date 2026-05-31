import json
import hashlib
from functools import lru_cache

def generate_cache_key(request_data: dict) -> str:
    """Generate a unique key for caching based on request data."""
    return hashlib.sha256(json.dumps(request_data, sort_keys=True).encode()).hexdigest()
