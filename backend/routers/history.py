from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from backend.database import get_db, ActivityLog, User
from backend.auth import get_current_user
from backend.schemas import ActivityLogResponse

router = APIRouter(prefix="/api/v1/history", tags=["history"])

@router.get("/", response_model=List[ActivityLogResponse])
def get_history(limit: int = 50, device_id: int = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(ActivityLog)
    
    if device_id:
        query = query.filter(ActivityLog.device_id == device_id)
        
    # Order by newest first
    logs = query.order_by(ActivityLog.timestamp.desc()).limit(limit).all()
    return logs

@router.delete("/")
def clear_history(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db.query(ActivityLog).delete()
    db.commit()
    return {"msg": "History cleared successfully"}
