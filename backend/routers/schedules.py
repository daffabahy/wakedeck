from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from backend.database import get_db, SessionLocal, Schedule, Device, ActivityLog, User
from backend.auth import get_current_user, decrypt_ssh_password
from backend.schemas import ScheduleCreate, ScheduleUpdate, ScheduleResponse
from backend.scheduler import add_schedule_job, remove_schedule_job, get_next_run_time
from backend.services.wol import wake_device
from backend.services.ssh import async_shutdown_device

router = APIRouter(prefix="/api/v1/schedules", tags=["schedules"])

async def execute_scheduled_task(schedule_id: int):
    """Callback function for APScheduler to run the actual tasks asynchronously."""
    db = SessionLocal()
    try:
        schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
        if not schedule or not schedule.enabled or not schedule.device:
            return
            
        device = schedule.device
        action = schedule.action.lower()
        
        status = "failed"
        message = ""
        
        if action == "wake":
            success, message = wake_device(device.mac_address)
            status = "success" if success else "failed"
            
        elif action == "shutdown":
            if device.ssh_user:
                pwd = decrypt_ssh_password(device.ssh_password)
                success, message = await async_shutdown_device(device.ip_address, device.ssh_user, pwd, 0, device.os_type or 'windows')
                status = "success" if success else "failed"
            else:
                message = "Missing SSH credentials for scheduled shutdown."

        log = ActivityLog(
            device_id=device.id, action=action, status=status,
            message=message, triggered_by="schedule", timestamp=datetime.utcnow()
        )
        db.add(log)
        db.commit()
    except Exception as e:
        print(f"Error in scheduled task {schedule_id}: {e}")
    finally:
        db.close()

def reload_schedule_into_scheduler(schedule: Schedule):
    if schedule.enabled:
        add_schedule_job(schedule.id, schedule.cron_expression, execute_scheduled_task)
    else:
        remove_schedule_job(schedule.id)

@router.get("/", response_model=List[ScheduleResponse])
def get_schedules(device_id: int = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(Schedule)
    if device_id:
        query = query.filter(Schedule.device_id == device_id)
    return query.all()

@router.post("/", response_model=ScheduleResponse)
def create_schedule(schedule: ScheduleCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_schedule = Schedule(
        device_id=schedule.device_id,
        cron_expression=schedule.cron_expression,
        action=schedule.action,
        enabled=schedule.enabled,
        label=schedule.label
    )
    db.add(db_schedule)
    db.commit()
    db.refresh(db_schedule)
    
    reload_schedule_into_scheduler(db_schedule)
    return db_schedule

@router.put("/{schedule_id}", response_model=ScheduleResponse)
def update_schedule(schedule_id: int, schedule_update: ScheduleUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
        
    schedule.cron_expression = schedule_update.cron_expression
    schedule.action = schedule_update.action
    schedule.enabled = schedule_update.enabled
    schedule.label = schedule_update.label
    
    db.commit()
    db.refresh(schedule)
    
    reload_schedule_into_scheduler(schedule)
    return schedule

@router.delete("/{schedule_id}")
def delete_schedule(schedule_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
        
    remove_schedule_job(schedule_id)
    
    db.delete(schedule)
    db.commit()
    return {"msg": "Schedule deleted successfully"}

@router.get("/{schedule_id}/next")
def get_schedule_next_run(schedule_id: int, current_user: User = Depends(get_current_user)):
    next_time = get_next_run_time(schedule_id)
    return {"next_run": next_time}
