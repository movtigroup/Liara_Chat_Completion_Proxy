import random
from sqlalchemy.orm import Session
from models import ProviderKey

def get_provider_key(db: Session, model: str):
    """
    Retrieves an active provider key for the given model.
    For now, it returns a random active key.
    Later we can add model-specific routing logic.
    """
    keys = db.query(ProviderKey).filter(ProviderKey.is_active == True).all()
    if not keys:
        return None

    # Simple weighted random or priority based selection
    # For now, let's just pick one with the highest priority
    max_priority = max(k.priority for k in keys)
    top_keys = [k for k in keys if k.priority == max_priority]
    return random.choice(top_keys)

def add_provider_key(db: Session, provider: str, api_key: str, priority: int = 1, config: dict = None):
    new_key = ProviderKey(provider=provider, api_key=api_key, priority=priority, config=config)
    db.add(new_key)
    db.commit()
    db.refresh(new_key)
    return new_key
