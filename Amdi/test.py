from pypylon import pylon
tl = pylon.TlFactory.GetInstance()
devs = tl.EnumerateDevices()
print(f'Trovate {len(devs)} camere:')
for d in devs:
    print(f'  Serial={d.GetSerialNumber()}  IP={d.GetIpAddress()}')
