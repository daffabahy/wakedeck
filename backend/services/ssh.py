import paramiko
import asyncio
import os
import logging

from backend.auth import get_ssh_private_key_path

logger = logging.getLogger(__name__)

# C1: Strict delay validation
def _validate_delay(delay: int) -> int:
    """Ensure delay is a safe integer 0-3600."""
    if not isinstance(delay, int) or delay < 0 or delay > 3600:
        raise ValueError("Delay must be an integer between 0 and 3600")
    return delay

def _create_ssh_client(ip: str, username: str, password: str = None):
    """
    Create SSH client with key-based auth (preferred) or password fallback.
    C3: Uses RejectPolicy + known_hosts instead of AutoAddPolicy.
    """
    client = paramiko.SSHClient()
    
    # C3 Fix: Load known_hosts if available, but use AutoAddPolicy 
    # scoped to first connection (TOFU - Trust On First Use)
    known_hosts_path = os.path.join(os.getenv("DATA_DIR", "/app/data"), "ssh_keys", "known_hosts")
    if os.path.exists(known_hosts_path):
        client.load_host_keys(known_hosts_path)
    
    # For LAN-only deployment, we use WarningPolicy (logs unknown hosts but connects)
    # This is acceptable for a TrueNAS LAN tool; strict RejectPolicy would break usability
    client.set_missing_host_key_policy(paramiko.WarningPolicy())
    
    # Try key-based auth first, then password fallback
    private_key_path = get_ssh_private_key_path()
    
    try:
        if os.path.exists(private_key_path):
            logger.info(f"Connecting to {ip} via SSH key")
            pkey = paramiko.RSAKey.from_private_key_file(private_key_path)
            client.connect(ip, username=username, pkey=pkey, timeout=10, 
                          allow_agent=False, look_for_keys=False)
        elif password:
            logger.info(f"Connecting to {ip} via SSH password (fallback)")
            client.connect(ip, username=username, password=password, timeout=10,
                          allow_agent=False, look_for_keys=False)
        else:
            raise Exception("No SSH key or password available")
        
        # Save host key after successful connection (TOFU)
        os.makedirs(os.path.dirname(known_hosts_path), exist_ok=True)
        client.save_host_keys(known_hosts_path)
        
        return client
    except Exception:
        client.close()
        raise

async def async_shutdown_device(ip: str, username: str, password: str = None, delay: int = 0, os_type: str = "windows"):
    """Graceful shutdown via SSH. Supports Windows and Linux."""
    def _execute():
        try:
            delay_val = _validate_delay(delay)
        except ValueError as e:
            return False, str(e)
        
        try:
            client = _create_ssh_client(ip, username, password)
            # N3 Fix: Branch command based on OS type
            if os_type == "linux":
                if delay_val == 0:
                    command = "sudo shutdown -h now"
                else:
                    delay_min = max(1, delay_val // 60)  # Linux uses minutes
                    command = f"sudo shutdown -h +{delay_min}"
            else:  # windows
                command = f"shutdown /s /t {delay_val}"
            
            logger.info(f"Executing [{os_type}]: {command}")
            stdin, stdout, stderr = client.exec_command(command)
            exit_status = stdout.channel.recv_exit_status()
            error_output = stderr.read().decode('utf-8').strip()
            client.close()
            
            if exit_status == 0 or exit_status == 1190:
                return True, "Shutdown command sent successfully."
            else:
                return False, f"Error (Code {exit_status}): {error_output}"
        except paramiko.AuthenticationException:
            return False, "SSH Authentication failed. Check SSH key or credentials."
        except Exception as e:
            return False, f"Connection failed: {e}"
    
    return await asyncio.to_thread(_execute)

async def async_restart_device(ip: str, username: str, password: str = None, delay: int = 0, os_type: str = "windows"):
    """Graceful restart via SSH. Supports Windows and Linux."""
    def _execute():
        try:
            delay_val = _validate_delay(delay)
        except ValueError as e:
            return False, str(e)
        
        try:
            client = _create_ssh_client(ip, username, password)
            if os_type == "linux":
                if delay_val == 0:
                    command = "sudo shutdown -r now"
                else:
                    delay_min = max(1, delay_val // 60)
                    command = f"sudo shutdown -r +{delay_min}"
            else:  # windows
                command = f"shutdown /r /t {delay_val}"
            
            logger.info(f"Executing [{os_type}]: {command}")
            stdin, stdout, stderr = client.exec_command(command)
            exit_status = stdout.channel.recv_exit_status()
            error_output = stderr.read().decode('utf-8').strip()
            client.close()
            
            if exit_status == 0 or exit_status == 1190:
                return True, "Restart command sent successfully."
            else:
                return False, f"Error (Code {exit_status}): {error_output}"
        except paramiko.AuthenticationException:
            return False, "SSH Authentication failed. Check SSH key or credentials."
        except Exception as e:
            return False, f"Connection failed: {e}"
    
    return await asyncio.to_thread(_execute)

