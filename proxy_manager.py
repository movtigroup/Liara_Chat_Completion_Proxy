import random
from sqlalchemy.orm import Session
import models

def get_best_proxy(db: Session, country: str = None):
    """
    Returns an active proxy. If country is specified, tries to find one from that country.
    """
    query = db.query(models.Proxy).filter(models.Proxy.is_active == True)
    if country:
        country_proxies = query.filter(models.Proxy.country == country).all()
        if country_proxies:
            return random.choice(country_proxies)

    all_active = query.all()
    return random.choice(all_active) if all_active else None

def format_proxy_url(proxy: models.Proxy):
    if not proxy: return None
    auth = ""
    if proxy.username and proxy.password:
        auth = f"{proxy.username}:{proxy.password}@"
    return f"{proxy.protocol}://{auth}{proxy.host}:{proxy.port}"
