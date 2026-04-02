from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.base import BaseHTTPMiddleware
import os
import contextlib
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

from backend.database import Base, engine, SessionLocal, Schedule
from backend.scheduler import start_scheduler
from backend.auth import ensure_ssh_keypair
from backend.routers import auth, devices, control, schedules, history, network, settings

Base.metadata.create_all(bind=engine)

# --- M6: Security Headers Middleware ---
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        # CSP: unsafe-inline needed because HTML uses onclick="" attributes
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
            "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
        # Prevent browser caching of JS/CSS (ensures fresh code after updates)
        path = request.url.path
        if path.endswith(('.js', '.css')):
            response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return response

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    ensure_ssh_keypair()  # Generate SSH keys if needed
    start_scheduler()
    
    db = SessionLocal()
    try:
        from backend.routers.schedules import reload_schedule_into_scheduler
        all_schedules = db.query(Schedule).all()
        for s in all_schedules:
            reload_schedule_into_scheduler(s)
        logging.getLogger(__name__).info(f"Loaded {len(all_schedules)} schedules")
    except Exception as e:
        logging.getLogger(__name__).error(f"Error loading schedules: {e}")
    finally:
        db.close()
    
    yield
    
    from backend.scheduler import scheduler
    if scheduler.running:
        scheduler.shutdown()

app = FastAPI(
    title="WakeDeck API",
    lifespan=lifespan,
    docs_url=None,     # Disable Swagger UI in production
    redoc_url=None,     # Disable ReDoc in production
    openapi_url=None,   # Disable OpenAPI schema
)

# C4: CORS removed — app serves frontend from same origin, no CORS needed
# Security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Routers
app.include_router(auth.router)
app.include_router(devices.router)
app.include_router(control.router)
app.include_router(schedules.router)
app.include_router(history.router)
app.include_router(network.router)
app.include_router(settings.router)

# Frontend
base_dir = os.path.dirname(os.path.dirname(__file__))
frontend_dir = os.path.join(base_dir, "frontend")

os.makedirs(frontend_dir, exist_ok=True)
os.makedirs(os.path.join(frontend_dir, "css"), exist_ok=True)
os.makedirs(os.path.join(frontend_dir, "js"), exist_ok=True)

@app.get("/")
@app.get("/login")
@app.get("/setup")
async def read_index():
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"msg": "Frontend not found."}

if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
