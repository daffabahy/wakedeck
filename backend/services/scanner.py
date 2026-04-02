import asyncio
import subprocess
import re
import platform
import logging

logger = logging.getLogger(__name__)

async def async_scan_network(subnet: str = None):
    """
    Scans the local network for devices.
    Strategy: nmap → arp-scan → arp table → ping sweep
    Fallbacks handle non-root contexts.
    """
    def _scan():
        target = subnet if subnet else _get_default_subnet()
        if not target:
            logger.warning("Could not determine subnet, using 192.168.1.0/24")
            target = "192.168.1.0/24"
        
        logger.info(f"Starting network scan on {target}")
        
        # 1. Try nmap (works as root)
        results = _try_nmap(target)
        if results:
            logger.info(f"nmap found {len(results)} devices")
            return results
        
        # 2. Try arp-scan (needs root)
        results = _try_arpscan()
        if results:
            logger.info(f"arp-scan found {len(results)} devices")
            return results
        
        # 3. Read existing ARP table (no root needed)
        results = _try_arp_table()
        if results:
            logger.info(f"ARP table has {len(results)} entries")
            return results
        
        logger.warning("All scan methods failed")
        return []

    return await asyncio.to_thread(_scan)

def _get_default_subnet():
    try:
        out = subprocess.run(['ip', 'route', 'show', 'default'],
                             capture_output=True, text=True, timeout=3)
        m = re.search(r'via\s+(\d+\.\d+\.\d+)\.\d+', out.stdout)
        if m:
            return f"{m.group(1)}.0/24"
        
        out = subprocess.run(['hostname', '-I'], capture_output=True, text=True, timeout=3)
        for ip in out.stdout.strip().split():
            if ip.startswith(('192.168.', '10.', '172.')):
                parts = ip.split('.')
                return f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
    except Exception as e:
        logger.debug(f"_get_default_subnet error: {e}")
    return None

def _try_nmap(target):
    try:
        out = subprocess.run(['nmap', '-sn', '-n', target],
                             capture_output=True, text=True, timeout=30)
        if out.returncode == 0:
            return _parse_nmap(out.stdout)
    except Exception as e:
        logger.debug(f"nmap failed: {e}")
    return []

def _try_arpscan():
    try:
        out = subprocess.run(['arp-scan', '--localnet', '-q'],
                             capture_output=True, text=True, timeout=15)
        if out.returncode == 0:
            results = []
            for line in out.stdout.strip().split('\n'):
                m = re.match(r'(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F:]+)', line)
                if m:
                    results.append({'ip': m.group(1), 'mac': m.group(2).lower()})
            return results
    except Exception as e:
        logger.debug(f"arp-scan failed: {e}")
    return []

def _try_arp_table():
    try:
        # Linux: ip neigh show
        out = subprocess.run(['ip', 'neigh', 'show'],
                             capture_output=True, text=True, timeout=5)
        if out.returncode == 0:
            results = []
            for line in out.stdout.strip().split('\n'):
                # Format: 192.168.1.1 dev eth0 lladdr aa:bb:cc:dd:ee:ff REACHABLE
                m = re.match(r'(\d+\.\d+\.\d+\.\d+)\s+.*lladdr\s+([0-9a-fA-F:]+)', line)
                if m:
                    mac = m.group(2).lower()
                    if mac not in ('00:00:00:00:00:00', 'ff:ff:ff:ff:ff:ff'):
                        results.append({'ip': m.group(1), 'mac': mac})
            return results if results else []
    except Exception as e:
        logger.debug(f"ip neigh failed: {e}")
    
    # Fallback: arp -n
    try:
        out = subprocess.run(['arp', '-n'], capture_output=True, text=True, timeout=5)
        if out.returncode == 0:
            results = []
            for line in out.stdout.strip().split('\n')[1:]:  # skip header
                m = re.match(r'(\d+\.\d+\.\d+\.\d+)\s+\S+\s+([0-9a-fA-F:]+)', line)
                if m:
                    mac = m.group(2).lower()
                    if mac not in ('00:00:00:00:00:00', 'ff:ff:ff:ff:ff:ff'):
                        results.append({'ip': m.group(1), 'mac': mac})
            return results if results else []
    except Exception as e:
        logger.debug(f"arp -n failed: {e}")
    return []

def _parse_nmap(output):
    results = []
    current_ip = None
    for line in output.split('\n'):
        ip_m = re.search(r'Nmap scan report for\s+(\d+\.\d+\.\d+\.\d+)', line)
        if ip_m:
            current_ip = ip_m.group(1)
        mac_m = re.search(r'MAC Address:\s+([0-9A-Fa-f:]+)', line)
        if mac_m and current_ip:
            results.append({'ip': current_ip, 'mac': mac_m.group(1).lower()})
            current_ip = None
    return results
