from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from datetime import datetime
import os

DATABASE_URL = "sqlite:///./data/wakedeck.db"

# Ensure data directory exists locally when running from python
os.makedirs("./data", exist_ok=True)

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, default="admin")
    password_hash = Column(String)
    api_key = Column(String, unique=True, index=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    mac_address = Column(String)
    ip_address = Column(String)
    os_type = Column(String, default="windows")
    ssh_user = Column(String, nullable=True)
    ssh_password = Column(String, nullable=True) # encrypted
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    schedules = relationship("Schedule", back_populates="device", cascade="all, delete")
    logs = relationship("ActivityLog", back_populates="device", cascade="all, delete")

class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"))
    cron_expression = Column(String)
    action = Column(String) # wake, shutdown
    enabled = Column(Boolean, default=True)
    label = Column(String, nullable=True)

    device = relationship("Device", back_populates="schedules")

class ActivityLog(Base):
    __tablename__ = "activity_log"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=True)
    action = Column(String) # wol, shutdown, ping, etc
    status = Column(String) # success, failed
    message = Column(Text, nullable=True)
    triggered_by = Column(String) # manual, schedule, api
    timestamp = Column(DateTime, default=datetime.utcnow)

    device = relationship("Device", back_populates="logs")

class Setting(Base):
    __tablename__ = "settings"

    key = Column(String, primary_key=True, index=True)
    value = Column(Text) # JSON encoded string

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
