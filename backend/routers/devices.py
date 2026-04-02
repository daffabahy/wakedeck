from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from backend.database import get_db, Device, User
from backend.auth import get_current_user, encrypt_ssh_password
from backend.schemas import DeviceCreate, DeviceUpdate, DeviceResponse

router = APIRouter(prefix="/api/v1/devices", tags=["devices"])

@router.get("/", response_model=List[DeviceResponse])
def get_devices(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    devices = db.query(Device).all()
    return devices

@router.get("/{device_id}", response_model=DeviceResponse)
def get_device(device_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device

@router.post("/", response_model=DeviceResponse)
def create_device(device: DeviceCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_device = Device(
        name=device.name,
        mac_address=device.mac_address,
        ip_address=device.ip_address,
        os_type=device.os_type,
        ssh_user=device.ssh_user,
        ssh_password=encrypt_ssh_password(device.ssh_password) if device.ssh_password else None,
        description=device.description
    )
    db.add(db_device)
    db.commit()
    db.refresh(db_device)
    return db_device

@router.put("/{device_id}", response_model=DeviceResponse)
def update_device(device_id: int, device_update: DeviceUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    device.name = device_update.name
    device.mac_address = device_update.mac_address
    device.ip_address = device_update.ip_address
    device.os_type = device_update.os_type
    device.ssh_user = device_update.ssh_user
    device.description = device_update.description
    
    # Update password only if provided
    if device_update.ssh_password:
        device.ssh_password = encrypt_ssh_password(device_update.ssh_password)
        
    db.commit()
    db.refresh(device)
    return device

@router.delete("/{device_id}")
def delete_device(device_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    db.delete(device)
    db.commit()
    return {"msg": "Device deleted successfully"}
