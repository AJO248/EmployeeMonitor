from sqlalchemy import BigInteger, Boolean, Column, DateTime, Integer, String, Text, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class LogEntry(Base):
    __tablename__ = "log_entries"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(128), nullable=True, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    url = Column(Text, nullable=True)
    domain = Column(String(255), nullable=True, index=True)
    title = Column(Text, nullable=True)
    app_name = Column(String(255), nullable=True, index=True)
    event_ts = Column(BigInteger, nullable=False, index=True)
    received_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True)
    username = Column(String(128), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RateLimit(Base):
    __tablename__ = "rate_limits"

    client_key = Column(String(128), primary_key=True, index=True)
    window_minute = Column(BigInteger, primary_key=True)
    request_count = Column(Integer, nullable=False, default=1)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

