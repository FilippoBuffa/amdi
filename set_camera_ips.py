"""
Set static persistent IPs on all 3 Basler GigE cameras and reboot them.
Run once, then update .env with the new IPs.
"""

import socket
import struct
from pypylon import pylon

CAMERAS = {
    "40724552": ("10.10.90.10", "Tracking"),
    "40784837": ("10.10.90.11", "Angle"),
    "40784971": ("10.10.90.12", "Inspection"),
}

SUBNET  = "255.255.0.0"
GATEWAY = "0.0.0.0"


def ip_int(ip: str) -> int:
    return struct.unpack("!I", socket.inet_aton(ip))[0]


def set_ip(serial: str, new_ip: str, label: str) -> None:
    tl   = pylon.TlFactory.GetInstance()
    devs = tl.EnumerateDevices()

    for info in devs:
        if info.GetSerialNumber() != serial:
            continue

        print(f"\n[{label}] Serial={serial}  Current IP={info.GetIpAddress()}")
        cam = pylon.InstantCamera(tl.CreateDevice(info))
        cam.Open()

        # Write persistent IP / subnet / gateway
        cam.GevPersistentIPAddress.SetValue(ip_int(new_ip))
        cam.GevPersistentSubnetMask.SetValue(ip_int(SUBNET))
        cam.GevPersistentDefaultGateway.SetValue(ip_int(GATEWAY))
        print(f"  Persistent IP set → {new_ip}")

        # Reboot so the new IP takes effect immediately
        try:
            cam.DeviceReset.Execute()
            print(f"  Camera rebooting...")
        except Exception:
            print(f"  DeviceReset not supported — power cycle required to apply new IP.")

        cam.Close()
        return

    print(f"\n[{label}] Serial={serial} NOT FOUND — check connection.")


if __name__ == "__main__":
    print("Setting static IPs on Basler cameras...\n")
    for serial, (ip, label) in CAMERAS.items():
        set_ip(serial, ip, label)
    print("\nDone. Wait ~10s for cameras to reboot, then verify with:")
    print("  python3 -c \"from pypylon import pylon; tl=pylon.TlFactory.GetInstance(); [print(d.GetSerialNumber(), d.GetIpAddress()) for d in tl.EnumerateDevices()]\"")
