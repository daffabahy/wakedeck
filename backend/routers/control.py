import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
import asyncio

from backend.database import get_db, Device, ActivityLog, Setting, User
from backend.auth import get_current_user, decrypt_ssh_password
from backend.services.wol import wake_device
from backend.services.ssh import async_shutdown_device, async_restart_device
from backend.services.ping import async_ping, async_check_port
from backend.services.notification import notify_discord, notify_telegram

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/control", tags=["control"])

def log_activity(db: Session, device_id: int, action: str, status: str, message: str, triggered_by: str = "manual"):
    log = ActivityLog(
        device_id=device_id, action=action, status=status,
        message=message, triggered_by=triggered_by, timestamp=datetime.utcnow()
    )
    db.add(log)
    db.commit()

async def send_notifications(db: Session, action: str, device_name: str, status: str, message: str):
    try:
        setting = db.query(Setting).filter(Setting.key == "webhook_settings").first()
        if not setting or not setting.value:
            return
        config = json.loads(setting.value)
        
        if action in ('wol', 'wake') and not config.get('notify_on_wake', True):
            return
        if action in ('shutdown', 'restart') and not config.get('notify_on_shutdown', True):
            return
        
        emoji = {'wol': '⚡', 'wake': '⚡', 'shutdown': '🔴', 'restart': '🔄'}.get(action, '📢')
        status_emoji = '✅' if status == 'success' else '❌'
        notif_msg = f"{emoji} **{action.upper()}** → {device_name}\n{status_emoji} Status: {status}\n📝 {message}"
        
        discord_url = config.get('discord_url')
        if discord_url and discord_url.startswith('https://discord.com/api/webhooks/'):
            await notify_discord(discord_url, notif_msg,
                               0x22c55e if status == 'success' else 0xef4444)
        
        tg_token = config.get('telegram_bot_token')
        tg_chat = config.get('telegram_chat_id')
        if tg_token and tg_chat:
            await notify_telegram(tg_token, tg_chat, notif_msg)
    except Exception as e:
        logger.error(f"Notification error: {e}")

@router.post("/{device_id}/wake")
async def wake_up_device(device_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    success, message = wake_device(device.mac_address)
    status_str = "success" if success else "failed"
    log_activity(db, device.id, "wol", status_str, message, "manual")
    asyncio.create_task(send_notifications(db, "wol", device.name, status_str, message))
    
    if not success:
        raise HTTPException(status_code=500, detail=message)
    return {"msg": f"Wake packet sent to {device.name}"}

@router.post("/{device_id}/shutdown")
async def shutdown_device(
    device_id: int,
    delay: int = Query(default=0, ge=0, le=3600),  # C1: validated range
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    if not device.ssh_user:
        raise HTTPException(status_code=400, detail="SSH credentials not configured")
    
    pwd = decrypt_ssh_password(device.ssh_password) if device.ssh_password else None
    success, message = await async_shutdown_device(device.ip_address, device.ssh_user, pwd, delay, device.os_type or 'windows')
    status_str = "success" if success else "failed"
    log_activity(db, device.id, "shutdown", status_str, message, "manual")
    asyncio.create_task(send_notifications(db, "shutdown", device.name, status_str, message))
    
    if not success:
        raise HTTPException(status_code=500, detail=message)
    return {"msg": f"Shutdown command sent to {device.name}"}

@router.post("/{device_id}/restart")
async def restart_device(
    device_id: int,
    delay: int = Query(default=0, ge=0, le=3600),  # C1: validated range
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    if not device.ssh_user:
        raise HTTPException(status_code=400, detail="SSH credentials not configured")
    
    pwd = decrypt_ssh_password(device.ssh_password) if device.ssh_password else None
    success, message = await async_restart_device(device.ip_address, device.ssh_user, pwd, delay, device.os_type or 'windows')
    status_str = "success" if success else "failed"
    log_activity(db, device.id, "restart", status_str, message, "manual")
    asyncio.create_task(send_notifications(db, "restart", device.name, status_str, message))
    
    if not success:
        raise HTTPException(status_code=500, detail=message)
    return {"msg": f"Restart command sent to {device.name}"}

@router.get("/{device_id}/status")
async def get_device_status(device_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    is_online = await async_ping(device.ip_address, timeout=2)
    
    if is_online:
        port_rdp, port_ssh, port_vnc = await asyncio.gather(
            async_check_port(device.ip_address, 3389, timeout=2),
            async_check_port(device.ip_address, 22, timeout=2),
            async_check_port(device.ip_address, 5900, timeout=2),
        )
    else:
        port_rdp = port_ssh = port_vnc = False
    
    return {
        "online": is_online,
        "rdp_open": port_rdp,
        "ssh_open": port_ssh,
        "vnc_open": port_vnc,
        "last_checked": datetime.utcnow().isoformat()
    }
