import asyncio
import socket
import platform
import logging

logger = logging.getLogger(__name__)

async def async_ping(ip_address: str, timeout: int = 2) -> bool:
    """
    Checks if a host is online using multiple methods:
    1. ICMP ping (system ping command)
    2. TCP port probe fallback (SSH 22, RDP 3389, HTTP 80, HTTPS 443)
    """
    # Try ICMP ping first
    icmp_result = await _icmp_ping(ip_address, timeout)
    if icmp_result:
        return True
    
    # Fallback: try common TCP ports to detect if host is up
    # (ICMP might be blocked by firewall but TCP ports are open)
    common_ports = [22, 3389, 5900, 445, 139, 80, 443, 8080]
    for port in common_ports:
        try:
            is_open = await _tcp_probe(ip_address, port, timeout=1)
            if is_open:
                logger.info(f"Host {ip_address} detected online via TCP port {port}")
                return True
        except Exception:
            continue
    
    return False

async def _icmp_ping(ip_address: str, timeout: int = 2) -> bool:
    """Try ICMP ping using system ping command."""
    current_os = platform.system().lower()
    if current_os == 'windows':
        param = '-n'
        timeout_param = '-w'
        timeout_val = str(timeout * 1000)
    else:
        param = '-c'
        timeout_param = '-W'
        timeout_val = str(timeout)

    try:
        proc = await asyncio.create_subprocess_exec(
            'ping', param, '1', timeout_param, timeout_val, ip_address,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout + 3)
        return proc.returncode == 0
    except asyncio.TimeoutError:
        logger.warning(f"Ping to {ip_address} timed out")
        try:
            proc.kill()
        except Exception:
            pass
        return False
    except Exception as e:
        logger.warning(f"Ping to {ip_address} failed: {e}")
        return False

async def _tcp_probe(ip_address: str, port: int, timeout: int = 1) -> bool:
    """Quick TCP connect probe to check if a port is reachable."""
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(ip_address, port),
            timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        return True
    except Exception:
        return False

async def async_check_port(ip_address: str, port: int, timeout: int = 2) -> bool:
    """
    Checks if a TCP port is open. Useful for RDP (3389), SSH (22), VNC (5900).
    """
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(ip_address, port),
            timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        return True
    except Exception:
        return False
