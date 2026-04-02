import re
from pydantic import BaseModel, field_validator
from typing import Optional, Literal
from datetime import datetime

class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str
    
    @field_validator('password')
    @classmethod
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v
    
    @field_validator('username')
    @classmethod
    def username_valid(cls, v):
        if not re.match(r'^[a-zA-Z0-9_]{3,32}$', v):
            raise ValueError('Username must be 3-32 alphanumeric characters')
        return v

class UserResponse(UserBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

# --- Validators for network fields ---

_MAC_RE = re.compile(r'^([0-9A-Fa-f]{2}[:\-]){5}[0-9A-Fa-f]{2}$')
_IP_RE = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$')
_SUBNET_RE = re.compile(r'^(\d{1,3}\.){3}\d{1,3}/\d{1,2}$')
_CRON_PART_RE = re.compile(r'^[\d\*,/\-]+$')

def _validate_mac(v: str) -> str:
    if not _MAC_RE.match(v):
        raise ValueError('Invalid MAC address format (expected AA:BB:CC:DD:EE:FF)')
    return v.upper().replace('-', ':')

def _validate_ip(v: str) -> str:
    if not _IP_RE.match(v):
        raise ValueError('Invalid IP address format')
    parts = v.split('.')
    for p in parts:
        if int(p) > 255:
            raise ValueError('Invalid IP address: octet > 255')
    return v

def _validate_subnet(v: str) -> str:
    if not _SUBNET_RE.match(v):
        raise ValueError('Invalid subnet format (expected x.x.x.x/xx)')
    ip_part, cidr = v.rsplit('/', 1)
    _validate_ip(ip_part)
    if int(cidr) > 32:
        raise ValueError('CIDR must be 0-32')
    return v

def _validate_cron(v: str) -> str:
    """Basic cron expression validation (5 parts)."""
    parts = v.strip().split()
    if len(parts) != 5:
        raise ValueError('Cron expression must have exactly 5 parts (min hour dom mon dow)')
    for part in parts:
        if not _CRON_PART_RE.match(part):
            raise ValueError(f'Invalid cron part: {part}')
    return v.strip()

class DeviceBase(BaseModel):
    name: str
    mac_address: str
    ip_address: str
    os_type: Literal["windows", "linux"] = "windows"
    ssh_user: Optional[str] = None
    description: Optional[str] = None
    
    @field_validator('mac_address')
    @classmethod
    def validate_mac(cls, v):
        return _validate_mac(v)
    
    @field_validator('ip_address')
    @classmethod
    def validate_ip(cls, v):
        return _validate_ip(v)
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        if len(v) > 100:
            raise ValueError('Device name too long (max 100)')
        # Strip HTML/script tags
        v = re.sub(r'<[^>]+>', '', v)
        return v.strip()

class DeviceCreate(DeviceBase):
    ssh_password: Optional[str] = None

class DeviceUpdate(DeviceBase):
    ssh_password: Optional[str] = None

class DeviceResponse(DeviceBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class ScheduleBase(BaseModel):
    cron_expression: str
    action: Literal["wake", "shutdown"] = "wake"  # M5: whitelist actions
    enabled: bool = True
    label: Optional[str] = None
    
    @field_validator('cron_expression')
    @classmethod
    def validate_cron(cls, v):
        return _validate_cron(v)

class ScheduleCreate(ScheduleBase):
    device_id: int

class ScheduleUpdate(ScheduleBase):
    pass

class ScheduleResponse(ScheduleBase):
    id: int
    device_id: int
    
    class Config:
        from_attributes = True

class ActivityLogResponse(BaseModel):
    id: int
    device_id: Optional[int]
    action: str
    status: str
    message: Optional[str]
    triggered_by: str
    timestamp: datetime

    class Config:
        from_attributes = True

class SetupStatusResponse(BaseModel):
    needs_setup: bool

class WebhookSettings(BaseModel):
    discord_url: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    notify_on_wake: bool = True
    notify_on_shutdown: bool = True
    notify_on_offline: bool = True
    
    @field_validator('discord_url')
    @classmethod
    def validate_discord_url(cls, v):
        """H4: SSRF protection — only allow Discord webhook URLs"""
        if v and not v.startswith('https://discord.com/api/webhooks/'):
            raise ValueError('Discord URL must start with https://discord.com/api/webhooks/')
        return v

class SubnetQuery(BaseModel):
    """Validated subnet for network scan."""
    subnet: str
    
    @field_validator('subnet')
    @classmethod
    def validate_subnet(cls, v):
        return _validate_subnet(v)
