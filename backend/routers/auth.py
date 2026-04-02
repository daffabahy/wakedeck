import time
import threading
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

from backend.database import get_db, User
from backend.auth import verify_password, get_password_hash, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES, get_current_user
from backend.schemas import UserCreate, Token, SetupStatusResponse

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# --- H1: Rate Limiting ---
_login_attempts = defaultdict(list)  # ip -> [timestamp, ...]
_lock = threading.Lock()
MAX_ATTEMPTS = 5
WINDOW_SECONDS = 60

def _rate_limit_check(client_ip: str):
    """Block if more than MAX_ATTEMPTS in WINDOW_SECONDS."""
    now = time.time()
    with _lock:
        # Clean old entries
        _login_attempts[client_ip] = [
            t for t in _login_attempts[client_ip] if now - t < WINDOW_SECONDS
        ]
        if len(_login_attempts[client_ip]) >= MAX_ATTEMPTS:
            raise HTTPException(
                status_code=429,
                detail=f"Too many login attempts. Try again in {WINDOW_SECONDS} seconds."
            )
        _login_attempts[client_ip].append(now)

@router.get("/setup-status", response_model=SetupStatusResponse)
def get_setup_status(db: Session = Depends(get_db)):
    """Check if system needs initial setup."""
    user_count = db.query(User).count()
    return {"needs_setup": user_count == 0}

@router.post("/setup")
def initial_setup(user: UserCreate, request: Request, db: Session = Depends(get_db)):
    """Create initial admin user. Only works if no users exist."""
    user_count = db.query(User).count()
    if user_count > 0:
        raise HTTPException(status_code=400, detail="Setup already completed")
    
    # Rate limit setup endpoint too
    _rate_limit_check(request.client.host)
    
    new_user = User(
        username=user.username,
        password_hash=get_password_hash(user.password)
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"msg": "Setup completed successfully"}

@router.post("/token", response_model=Token)
def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """OAuth2 login with rate limiting."""
    # H1: Rate limit by client IP
    _rate_limit_check(request.client.host)
    
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {"username": current_user.username, "id": current_user.id}
