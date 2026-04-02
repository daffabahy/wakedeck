from wakeonlan import send_magic_packet
import sys

def wake_device(mac_address: str, broadcast_ip: str = "255.255.255.255"):
    """
    Sends a Wake-on-LAN magic packet to the given MAC address.
    Because network_mode is host, we can broadcast this to the entire LAN.
    """
    try:
        # Default broadcast usually works for network_mode: host
        send_magic_packet(mac_address, ip_address=broadcast_ip)
        return True, "Magic packet sent successfully"
    except Exception as e:
        return False, f"Failed to send WoL packet: {str(e)}"
