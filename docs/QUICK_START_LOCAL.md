# Quick Start: Local Network Setup (No VPN)

**Simplest setup for accessing dashboard on your local WiFi network.**

---

## 🎯 What This Does

- ✅ Dashboard accessible from any device on your WiFi
- ✅ No VPN needed
- ✅ No internet exposure (maximum security)
- ✅ Works with Next.js or Vite/React SPA

---

## Step 1: Find Your Local IP

**Windows:**
```powershell
ipconfig
# Look for "IPv4 Address" under your WiFi adapter
# Example: 192.168.1.100
```

**Linux/Mac:**
```bash
ifconfig
# or
ip addr show
```

---

## Step 2: Update Configuration

**Edit `.env` file:**
```env
# Use your local IP (not 0.0.0.0)
SERVER_IP=192.168.1.100
SERVER_PORT=8080

# FastAPI Dashboard API
API_HOST=192.168.1.100
API_PORT=8000

# Next.js Dashboard
DASHBOARD_HOST=192.168.1.100
DASHBOARD_PORT=3000
```

---

## Step 3: Configure Firewall (Windows)

**PowerShell (Run as Administrator):**
```powershell
# Allow local network access only
New-NetFirewallRule -DisplayName "Dashboard API" `
    -Direction Inbound -LocalPort 8000 -Protocol TCP `
    -Action Allow -Profile Private

New-NetFirewallRule -DisplayName "Dashboard Frontend" `
    -Direction Inbound -LocalPort 3000 -Protocol TCP `
    -Action Allow -Profile Private

# Block from Public network
Set-NetFirewallRule -DisplayName "Dashboard API" -Profile Public -Action Block
Set-NetFirewallRule -DisplayName "Dashboard Frontend" -Profile Public -Action Block
```

---

## Step 4: Update CORS (FastAPI)

**In `src/mt5-python_server/src/api/main.py`:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        f"http://192.168.1.100:3000",  # Your local IP
        "http://localhost:3000",        # Local dev
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Step 5: Start Services

```bash
# Start everything
docker compose up -d

# Or start individually
# Backend API
cd src/mt5-python_server
python -m uvicorn src.api.main:app --host 192.168.1.100 --port 8000

# Frontend
cd src/dashboard
npm run dev -- --host 192.168.1.100
```

---

## Step 6: Access Dashboard

**From any device on your WiFi:**
```
http://192.168.1.100:3000
```

**From the server itself:**
```
http://localhost:3000
```

---

## ✅ Done!

Your dashboard is now accessible from any device on your local network.

**Need remote access later?** See `DEPLOYMENT_OPTIONS.md` for VPN or SPA deployment options.

---

## Troubleshooting

**Can't access from phone?**
- Make sure phone is on same WiFi network
- Check firewall rules (should allow Private network)
- Verify IP address is correct

**Connection refused?**
- Check if services are running: `docker compose ps`
- Check firewall: `Get-NetFirewallRule -DisplayName "Dashboard*"`
- Verify IP binding: `netstat -an | findstr 8000`

**CORS errors?**
- Make sure CORS origins include your device's IP
- Check browser console for exact error

---

*For SPA deployment or VPN setup, see `DEPLOYMENT_OPTIONS.md`*
