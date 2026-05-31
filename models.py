from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from database import Base
import datetime

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    api_keys = relationship("APIKey", back_populates="owner")
    usage_logs = relationship("UsageLog", back_populates="user")

class APIKey(Base):
    __tablename__ = "api_keys"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True)
    name = Column(String)
    user_id = Column(Integer, ForeignKey("users.id"))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    owner = relationship("User", back_populates="api_keys")

class ProviderKey(Base):
    __tablename__ = "provider_keys"
    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String) # e.g., 'openai', 'anthropic', 'google'
    api_key = Column(String)
    priority = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    config = Column(JSON, nullable=True) # For additional settings like base_url
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class UsageLog(Base):
    __tablename__ = "usage_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    model = Column(String)
    request_tokens = Column(Integer, default=0)
    response_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    cost = Column(Float, default=0.0)
    request_data = Column(JSON)
    response_data = Column(JSON)
    status_code = Column(Integer)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="usage_logs")

class Proxy(Base):
    __tablename__ = "proxies"
    id = Column(Integer, primary_key=True, index=True)
    host = Column(String, index=True)
    port = Column(Integer)
    protocol = Column(String, default="http") # http, socks5
    username = Column(String, nullable=True)
    password = Column(String, nullable=True)
    country = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationship to specific providers if needed
    # provider_keys = relationship("ProviderKey", back_populates="proxy")
