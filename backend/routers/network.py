import re
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Any, Optional

from backend.database import get_db, User
from backend.auth import get_current_user
from backend.services.scanner import async_scan_network

router = APIRouter(prefix="/api/v1/network", tags=["network"])

# C2: Strict subnet validation regex
_SUBNET_RE = re.compile(r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})/(\d{1,2})$')

def _validate_subnet(subnet: str) -> str:
    """Validate subnet format to prevent command injection via nmap."""
    m = _SUBNET_RE.match(subnet)
    if not m:
        raise HTTPException(400, "Invalid subnet format. Expected: x.x.x.x/xx")
    # Validate each octet
    for i in range(1, 5):
        if int(m.group(i)) > 255:
            raise HTTPException(400, "Invalid IP octet > 255")
    if int(m.group(5)) > 32:
        raise HTTPException(400, "Invalid CIDR (0-32)")
    return subnet

@router.get("/scan", response_model=List[Dict[str, Any]])
async def scan_network(
    subnet: Optional[str] = Query(default=None, max_length=18),
    current_user: User = Depends(get_current_user)
):
    """Scan local network for devices. Subnet is validated to prevent injection."""
    validated_subnet = None
    if subnet:
        validated_subnet = _validate_subnet(subnet)
    
    try:
        results = await async_scan_network(validated_subnet)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")
