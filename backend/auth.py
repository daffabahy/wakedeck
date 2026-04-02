import os
import logging
from datetime import datetime, timedelta
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from backend.database import get_db, User
import bcrypt
import base64
import hashlib

logger = logging.getLogger(__name__)

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "changeme_to_a_secure_random_string")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 4  # H2: Reduced from 7 days to 4 hours

# Fernet encryption for legacy SSH passwords (C5: will migrate to key-based)
fernet_key = base64.urlsafe_b64encode(hashlib.sha256(SECRET_KEY.encode()).digest())
cipher_suite = Fernet(fernet_key)

# SSH Key paths
SSH_KEY_DIR = os.path.join(os.getenv("DATA_DIR", "/app/data"), "ssh_keys")
SSH_PRIVATE_KEY_PATH = os.path.join(SSH_KEY_DIR, "id_rsa")
SSH_PUBLIC_KEY_PATH = os.path.join(SSH_KEY_DIR, "id_rsa.pub")

# OAuth2 Scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)  # Increased from default 10
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def encrypt_ssh_password(password: str) -> str:
    if not password:
        return ""
    return cipher_suite.encrypt(password.encode('utf-8')).decode('utf-8')

def decrypt_ssh_password(encrypted_password: str) -> str:
    if not encrypted_password:
        return ""
    try:
        return cipher_suite.decrypt(encrypted_password.encode('utf-8')).decode('utf-8')
    except Exception:
        return ""

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

# --- SSH Key Management (C3/C5 fix) ---

def ensure_ssh_keypair():
    """Generate SSH keypair if it doesn't exist. Called on startup."""
    try:
        os.makedirs(SSH_KEY_DIR, exist_ok=True)
        
        if os.path.exists(SSH_PRIVATE_KEY_PATH) and os.path.exists(SSH_PUBLIC_KEY_PATH):
            logger.info(f"SSH keypair already exists at {SSH_KEY_DIR}")
            return
        
        logger.info(f"Generating new SSH keypair at {SSH_KEY_DIR}...")
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=4096,
        )
        
        # Save private key
        with open(SSH_PRIVATE_KEY_PATH, 'wb') as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.OpenSSH,
                encryption_algorithm=serialization.NoEncryption()
            ))
        
        try:
            os.chmod(SSH_PRIVATE_KEY_PATH, 0o600)
        except OSError:
            logger.warning("Could not chmod private key (non-critical on some OS)")
        
        # Save public key
        public_key = private_key.public_key()
        pub_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.OpenSSH,
            format=serialization.PublicFormat.OpenSSH
        )
        with open(SSH_PUBLIC_KEY_PATH, 'wb') as f:
            f.write(pub_bytes)
        
        logger.info(f"SSH keypair generated successfully at {SSH_KEY_DIR}")
    except Exception as e:
        logger.error(f"Failed to generate SSH keypair: {e}")
        logger.error(f"SSH_KEY_DIR={SSH_KEY_DIR}, writable={os.access(os.path.dirname(SSH_KEY_DIR), os.W_OK)}")

def get_ssh_public_key() -> str:
    """Read the public key for display to user."""
    try:
        if not os.path.exists(SSH_PUBLIC_KEY_PATH):
            logger.info("Public key not found, attempting to generate...")
            ensure_ssh_keypair()
        if os.path.exists(SSH_PUBLIC_KEY_PATH):
            with open(SSH_PUBLIC_KEY_PATH, 'r') as f:
                return f.read().strip()
        return "Error: SSH key could not be generated. Check container logs and ensure /app/data is writable."
    except Exception as e:
        return f"Error reading SSH key: {e}"

def get_ssh_private_key_path() -> str:
    """Return path to private key for Paramiko."""
    if not os.path.exists(SSH_PRIVATE_KEY_PATH):
        ensure_ssh_keypair()
    return SSH_PRIVATE_KEY_PATH
