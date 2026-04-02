import json
import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from typing import Optional, Literal
from sqlalchemy.orm import Session

from backend.database import get_db, Setting, User
from backend.auth import get_current_user, get_ssh_public_key
from backend.schemas import WebhookSettings
from backend.services.notification import notify_discord, notify_telegram

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])

def _mask_secret(value: str, show_last: int = 6) -> str:
    """Mask a secret value, showing only last N characters."""
    if not value or len(value) <= show_last:
        return "••••••"
    return "••••••" + value[-show_last:]

# --- SSH Key Endpoint ---
@router.get("/ssh-public-key")
def get_public_key(current_user: User = Depends(get_current_user)):
    """Returns the public SSH key for user to install on target machines."""
    try:
        pub_key = get_ssh_public_key()
        return {"public_key": pub_key}
    except Exception as e:
        raise HTTPException(500, f"Could not read SSH key: {str(e)}")

# --- Webhook Settings ---

class WebhookSettingsMasked(BaseModel):
    """Response model with masked secrets."""
    discord_configured: bool = False
    discord_hint: Optional[str] = None
    telegram_configured: bool = False
    telegram_hint: Optional[str] = None
    notify_on_wake: bool = True
    notify_on_shutdown: bool = True
    notify_on_offline: bool = True

@router.get("/webhook")
def get_webhook_settings(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Returns webhook settings with masked secrets — URLs/tokens are NOT returned."""
    setting = db.query(Setting).filter(Setting.key == "webhook_settings").first()
    if setting and setting.value:
        try:
            data = json.loads(setting.value)
            discord_url = data.get('discord_url')
            tg_token = data.get('telegram_bot_token')
            tg_chat = data.get('telegram_chat_id')
            return {
                "discord_configured": bool(discord_url),
                "discord_hint": _mask_secret(discord_url) if discord_url else None,
                "telegram_configured": bool(tg_token and tg_chat),
                "telegram_hint": _mask_secret(tg_chat) if tg_chat else None,
                "notify_on_wake": data.get('notify_on_wake', True),
                "notify_on_shutdown": data.get('notify_on_shutdown', True),
                "notify_on_offline": data.get('notify_on_offline', True),
            }
        except json.JSONDecodeError:
            pass
    return WebhookSettingsMasked()

@router.put("/webhook")
def update_webhook_settings(settings: WebhookSettings, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Merge new webhook settings with existing ones (so saving Discord doesn't erase Telegram)."""
    setting = db.query(Setting).filter(Setting.key == "webhook_settings").first()
    
    # Load existing settings to merge
    existing = {}
    if setting and setting.value:
        try:
            existing = json.loads(setting.value)
        except json.JSONDecodeError:
            pass
    
    # Merge: only update fields that are provided (not None)
    new_data = settings.model_dump() if hasattr(settings, 'model_dump') else settings.dict()
    for key, value in new_data.items():
        if value is not None:
            existing[key] = value
    
    # Always update trigger booleans
    for key in ('notify_on_wake', 'notify_on_shutdown', 'notify_on_offline'):
        existing[key] = new_data[key]
    
    json_val = json.dumps(existing)
    if setting:
        setting.value = json_val
    else:
        setting = Setting(key="webhook_settings", value=json_val)
        db.add(setting)
    db.commit()
    return {"msg": "Webhook settings saved"}

@router.delete("/webhook/discord")
def clear_discord_webhook(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Remove Discord webhook configuration."""
    setting = db.query(Setting).filter(Setting.key == "webhook_settings").first()
    if setting and setting.value:
        data = json.loads(setting.value)
        data['discord_url'] = None
        setting.value = json.dumps(data)
        db.commit()
    return {"msg": "Discord webhook cleared"}

@router.delete("/webhook/telegram")
def clear_telegram_bot(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Remove Telegram bot configuration."""
    setting = db.query(Setting).filter(Setting.key == "webhook_settings").first()
    if setting and setting.value:
        data = json.loads(setting.value)
        data['telegram_bot_token'] = None
        data['telegram_chat_id'] = None
        setting.value = json.dumps(data)
        db.commit()
    return {"msg": "Telegram bot cleared"}

# --- Timezone Setting ---
@router.get("/timezone")
def get_timezone(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    setting = db.query(Setting).filter(Setting.key == "timezone").first()
    return {"timezone": setting.value if setting else "UTC+0"}

class TimezoneRequest(BaseModel):
    timezone: str = "UTC+0"
    
    @field_validator('timezone')
    @classmethod
    def validate_tz(cls, v):
        if not re.match(r'^UTC[+-]\d{1,2}$', v):
            raise ValueError('Invalid timezone format. Use UTC+N or UTC-N')
        offset = int(v.replace('UTC', ''))
        if offset < -12 or offset > 14:
            raise ValueError('Timezone offset must be between -12 and +14')
        return v

@router.put("/timezone")
def set_timezone(data: TimezoneRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    setting = db.query(Setting).filter(Setting.key == "timezone").first()
    if setting:
        setting.value = data.timezone
    else:
        db.add(Setting(key="timezone", value=data.timezone))
    db.commit()
    return {"timezone": data.timezone}

# --- Test Notifications ---
class TestNotificationRequest(BaseModel):
    type: Literal["discord", "telegram"]
    url: Optional[str] = None
    bot_token: Optional[str] = None
    chat_id: Optional[str] = None

@router.post("/test-notification")
async def test_notification(req: TestNotificationRequest, current_user: User = Depends(get_current_user)):
    msg = "🔔 WakeDeck test notification — if you see this, it works!"
    
    if req.type == 'discord':
        if not req.url:
            raise HTTPException(400, "Webhook URL required")
        if not req.url.startswith('https://discord.com/api/webhooks/'):
            raise HTTPException(400, "URL must be a Discord webhook (https://discord.com/api/webhooks/...)")
        ok, detail = await notify_discord(req.url, msg)
        if not ok:
            raise HTTPException(500, f"Discord failed: {detail}")
        return {"msg": "Discord test sent"}
    
    elif req.type == 'telegram':
        if not req.bot_token or not req.chat_id:
            raise HTTPException(400, "Bot token and chat ID required")
        if not re.match(r'^\d+:[A-Za-z0-9_-]+$', req.bot_token):
            raise HTTPException(400, "Invalid Telegram bot token format")
        ok, detail = await notify_telegram(req.bot_token, req.chat_id, msg)
        if not ok:
            raise HTTPException(500, f"Telegram failed: {detail}")
        return {"msg": "Telegram test sent"}
    
    raise HTTPException(400, "Unknown notification type")
