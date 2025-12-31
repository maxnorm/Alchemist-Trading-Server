# Local-Only Setup Guide (No VPN Required)

## Why VPN Was Mentioned

**Tailscale VPN is ONLY needed for remote access** (outside your home network).

**For local network access** (same WiFi), **you don't need VPN at all!**

## Local-Only Architecture

```
Your Local Network (WiFi)
├── Your PC (Browser) ──┐
├── Old Desktop (Server)│── All on 192.168.x.x
└── Phone/Tablet ──────┘
```

## Setup Steps

### 1. Find Server IP
```powershell
# On old desktop
ipconfig
# Note the IPv4 Address (e.g., 192.168.1.100)
```

### 2. Configure FastAPI
```python
# api/config.py
api_host: str = "192.168.1.100"  # Your server's local IP
api_port: int = 8000
```

### 3. Configure CORS
```python
allow_origins=[
    "http://localhost:3000",
    "http://192.168.1.50:3000",  # Your PC
    "http://192.168.1.100:3000",  # Server
]
```

### 4. Configure Frontend
```env
# .env.local
NEXT_PUBLIC_API_URL=http://192.168.1.100:8000
NEXT_PUBLIC_WS_URL=ws://192.168.1.100:8000
```

### 5. Windows Firewall (Run as Admin)
```powershell
New-NetFirewallRule -DisplayName "FastAPI" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "Next.js" -Direction Inbound -LocalPort 3000 -Protocol TCP -Action Allow
```

### 6. Access Dashboard
- From PC: `http://192.168.1.100:3000`
- From Phone (same WiFi): `http://192.168.1.100:3000`

## Security (Still Required)

- ✅ JWT + 2FA authentication
- ✅ Strong WiFi password
- ✅ Firewall blocks external access
- ✅ HTTPS optional (HTTP OK for local)

## When You Need VPN

Only if you want access from:
- Outside your home
- Coffee shop
- Office
- Traveling

Then install Tailscale (optional).

## Benefits of Local-Only

- ✅ Simpler (no VPN software)
- ✅ Faster (direct LAN)
- ✅ More secure (zero internet exposure)
- ✅ Free (no dependencies)
