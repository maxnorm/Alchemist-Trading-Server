# Deployment Options Guide
# Trading Dashboard - Deployment Strategies

**Last Updated:** December 31, 2024

---

## Table of Contents

1. [Why Tailscale VPN?](#why-tailscale-vpn)
2. [Option 1: Local Network Only (No VPN)](#option-1-local-network-only-no-vpn)
3. [Option 2: SPA Deployment (Vite/React)](#option-2-spa-deployment-vitereact)
4. [Option 3: VPN for Remote Access](#option-3-vpn-for-remote-access)
5. [Comparison Matrix](#comparison-matrix)
6. [Quick Setup Guides](#quick-setup-guides)

---

## Why Tailscale VPN?

**Tailscale VPN was recommended** because it provides:
- ✅ **Zero-configuration** secure remote access
- ✅ **No port forwarding** needed (no router configuration)
- ✅ **Encrypted tunnel** (WireGuard-based)
- ✅ **Free tier** (up to 100 devices)
- ✅ **Works behind NAT/firewalls** automatically

**However**, it's **NOT required** if you:
- Only need access from your local network (same WiFi)
- Want to deploy as a static SPA (hosted elsewhere)
- Prefer a simpler setup

---

## Option 1: Local Network Only (No VPN)

### ✅ Best For
- Accessing dashboard from devices on the same WiFi
- Maximum security (no internet exposure)
- Simplest setup

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    YOUR LOCAL NETWORK                    │
│                                                          │
│  ┌─────────────┐         ┌──────────────────────────┐  │
│  │   Your PC   │         │   Old Desktop (Server)   │  │
│  │  (Browser)  │◄───────►│                          │  │
│  └─────────────┘   LAN   │  FastAPI :8000           │  │
│                          │  Next.js :3000            │  │
│  ┌─────────────┐         │  Python Server :8080      │  │
│  │   Phone     │◄───────►│  MariaDB :3306           │  │
│  │  (Browser)  │   WiFi  └──────────────────────────┘  │
│  └─────────────┘                                        │
│                                                          │
│  LAN IP: 192.168.1.100 (example)                        │
└─────────────────────────────────────────────────────────┘
                          │
                    ❌ FIREWALL ❌
                          │
                   ┌──────▼──────┐
                   │   INTERNET  │
                   │  (Blocked)  │
                   └─────────────┘
```

### Setup Steps

#### 1. Configure Server to Bind to Local IP

**Update `.env`:**
```env
# Use your desktop's local IP (not 0.0.0.0)
SERVER_IP=192.168.1.100
SERVER_PORT=8080

# FastAPI Dashboard API
API_HOST=192.168.1.100
API_PORT=8000

# Next.js Dashboard (if running separately)
DASHBOARD_HOST=192.168.1.100
DASHBOARD_PORT=3000
```

**Find your local IP:**
```bash
# Windows
ipconfig
# Look for "IPv4 Address" under your WiFi adapter

# Linux/Mac
ifconfig
# or
ip addr show
```

#### 2. Configure Windows Firewall

**Allow local network access only:**

```powershell
# PowerShell (Run as Administrator)

# Allow FastAPI on port 8000 (local network only)
New-NetFirewallRule -DisplayName "Dashboard API" `
    -Direction Inbound -LocalPort 8000 -Protocol TCP `
    -Action Allow -Profile Private

# Allow Next.js on port 3000 (local network only)
New-NetFirewallRule -DisplayName "Dashboard Frontend" `
    -Direction Inbound -LocalPort 3000 -Protocol TCP `
    -Action Allow -Profile Private

# Block from Public network
Set-NetFirewallRule -DisplayName "Dashboard API" -Profile Public -Action Block
Set-NetFirewallRule -DisplayName "Dashboard Frontend" -Profile Public -Action Block
```

#### 3. Update FastAPI CORS

**In `src/mt5-python_server/src/api/main.py`:**
```python
from fastapi.middleware.cors import CORSMiddleware

# Get local network IP range (e.g., 192.168.1.0/24)
LOCAL_NETWORK = "192.168.1.0/24"

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://192.168.1.100:3000",  # Your desktop IP
        "http://localhost:3000",      # Local development
        # Add other device IPs as needed
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

#### 4. Access Dashboard

**From any device on your WiFi:**
```
http://192.168.1.100:3000
```

### ✅ Pros
- ✅ **Simplest setup** - no VPN needed
- ✅ **Maximum security** - no internet exposure
- ✅ **Fast** - local network latency
- ✅ **No external dependencies**

### ❌ Cons
- ❌ **No remote access** - only works on same WiFi
- ❌ **IP changes** - need to update if router assigns new IP

---

## Option 2: SPA Deployment (Vite/React)

### ✅ Best For
- Deploying frontend to static hosting (Vercel, Netlify, GitHub Pages)
- Separating frontend from backend
- Public or semi-public access (with authentication)

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    INTERNET / CLOUD                      │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │         Static Hosting (Vercel/Netlify)          │   │
│  │                                                   │   │
│  │  ┌─────────────────────────────────────────────┐ │   │
│  │  │  SPA Frontend (Vite/React)                 │ │   │
│  │  │  - Built static files                       │ │   │
│  │  │  - Login page                               │ │   │
│  │  │  - Dashboard UI                             │ │   │
│  │  └─────────────────────────────────────────────┘ │   │
│  │                                                   │   │
│  │  URL: https://your-dashboard.vercel.app         │   │
│  └──────────────────────────────────────────────────┘   │
│                          │                                │
│                          │ HTTPS API Calls                │
│                          ▼                                │
│  ┌──────────────────────────────────────────────────┐   │
│  │         Your Home Network                        │   │
│  │                                                   │   │
│  │  ┌─────────────────────────────────────────────┐ │   │
│  │  │  Old Desktop (Server)                      │ │   │
│  │  │  FastAPI :8000                             │ │   │
│  │  │  Python Server :8080                       │ │   │
│  │  │  MariaDB :3306                             │ │   │
│  │  └─────────────────────────────────────────────┘ │   │
│  │                                                   │   │
│  │  ⚠️ Must expose API to internet (HTTPS required) │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### Setup Steps

#### 1. Convert Next.js to Vite/React SPA

**Option A: Use Vite (Recommended)**

```bash
# Create new Vite project
npm create vite@latest dashboard-spa -- --template react-ts

cd dashboard-spa
npm install

# Install dependencies
npm install lightweight-charts @tanstack/react-query zustand axios
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p

# Install shadcn/ui (compatible with Vite)
npx shadcn-ui@latest init
```

**Option B: Export Next.js as Static**

```bash
# In Next.js project
# next.config.js
module.exports = {
  output: 'export',  // Static export
  trailingSlash: true,
}

# Build
npm run build
# Output: out/ folder with static files
```

#### 2. Configure API Endpoint

**In your SPA code:**
```typescript
// src/lib/api.ts
const API_URL = import.meta.env.VITE_API_URL || 'http://192.168.1.100:8000';

export const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});
```

**Environment file (`.env.production`):**
```env
VITE_API_URL=https://your-api-domain.com
```

#### 3. Expose FastAPI to Internet (HTTPS Required!)

**Option A: Use Cloudflare Tunnel (Free, No Port Forwarding)**

```bash
# Install cloudflared
# Windows: Download from https://github.com/cloudflare/cloudflared/releases
# Or use Docker

# Create tunnel
cloudflared tunnel create trading-api

# Configure tunnel
cloudflared tunnel route dns trading-api api.yourdomain.com

# Run tunnel
cloudflared tunnel run trading-api
```

**Option B: Use ngrok (Free tier available)**

```bash
# Install ngrok
# https://ngrok.com/download

# Expose FastAPI
ngrok http 8000

# Use the HTTPS URL provided (e.g., https://abc123.ngrok.io)
```

**Option C: Port Forwarding + Dynamic DNS**

1. Configure router port forwarding (8000 → your desktop)
2. Use dynamic DNS service (DuckDNS, No-IP)
3. Set up Let's Encrypt SSL certificate

#### 4. Update CORS for Production

**In FastAPI:**
```python
# Allow your SPA domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://your-dashboard.vercel.app",
        "https://your-dashboard.netlify.app",
        # Add your production domains
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

#### 5. Deploy SPA

**Vercel:**
```bash
npm install -g vercel
vercel --prod
```

**Netlify:**
```bash
npm install -g netlify-cli
netlify deploy --prod
```

**GitHub Pages:**
```bash
# Build first
npm run build

# Deploy to gh-pages branch
npm install -g gh-pages
gh-pages -d dist
```

### ✅ Pros
- ✅ **Professional deployment** - hosted on CDN
- ✅ **Fast loading** - static files from edge
- ✅ **Scalable** - handles traffic spikes
- ✅ **Free hosting** - Vercel/Netlify free tiers

### ❌ Cons
- ❌ **API must be exposed** - requires HTTPS + security
- ❌ **More complex** - need to manage API exposure
- ❌ **Potential latency** - API calls go over internet
- ❌ **Security concerns** - API accessible from internet

---

## Option 3: VPN for Remote Access

### ✅ Best For
- Accessing dashboard from anywhere (phone, laptop, etc.)
- Maximum security without exposing to internet
- Zero-configuration remote access

### Setup Steps

#### 1. Install Tailscale

**On Server (Old Desktop):**
```bash
# Windows: Download installer from tailscale.com
# Or use winget
winget install Tailscale.Tailscale

# Linux
curl -fsSL https://tailscale.com/install.sh | sh

# Start
tailscale up
```

**On Client Devices:**
- Install Tailscale app (iOS/Android/Windows/Mac)
- Sign in with same account
- Devices automatically connect

#### 2. Get Tailscale IP

```bash
# On server
tailscale ip
# Returns: 100.x.x.x (Tailscale IP)
```

#### 3. Update Configuration

**Bind to Tailscale IP:**
```env
# .env
API_HOST=100.x.x.x  # Your Tailscale IP
API_PORT=8000
```

**Or bind to both local and Tailscale:**
```python
# In FastAPI
import socket

# Get Tailscale IP
tailscale_ip = socket.gethostbyname(socket.gethostname())

# Or bind to 0.0.0.0 and use firewall rules
uvicorn.run(app, host="0.0.0.0", port=8000)
```

#### 4. Access Dashboard

**From any device with Tailscale:**
```
http://100.x.x.x:3000
```

### ✅ Pros
- ✅ **Access from anywhere** - phone, laptop, etc.
- ✅ **Secure** - encrypted tunnel, no port forwarding
- ✅ **Easy setup** - zero configuration
- ✅ **Free** - up to 100 devices

### ❌ Cons
- ❌ **Requires Tailscale** - external dependency
- ❌ **Slight overhead** - VPN adds minimal latency

---

## Comparison Matrix

| Feature | Local Only | SPA Deployment | VPN (Tailscale) |
|---------|-----------|----------------|-----------------|
| **Setup Complexity** | ⭐ Easy | ⭐⭐⭐ Complex | ⭐⭐ Medium |
| **Remote Access** | ❌ No | ✅ Yes | ✅ Yes |
| **Internet Exposure** | ❌ None | ⚠️ API exposed | ❌ None |
| **Security** | ✅✅✅ High | ⚠️ Medium | ✅✅✅ High |
| **Cost** | ✅ Free | ✅ Free (hosting) | ✅ Free |
| **Latency** | ✅ Low | ⚠️ Medium | ✅ Low |
| **Port Forwarding** | ❌ Not needed | ⚠️ May need | ❌ Not needed |
| **Best For** | Same WiFi only | Public access | Remote access |

---

## Quick Setup Guides

### Local Network Only (Recommended for Start)

```bash
# 1. Find your local IP
ipconfig  # Windows
ifconfig  # Linux/Mac

# 2. Update .env
SERVER_IP=192.168.1.100
API_HOST=192.168.1.100
API_PORT=8000

# 3. Start services
docker compose up -d

# 4. Access from any device on WiFi
# http://192.168.1.100:3000
```

### SPA with Vite

```bash
# 1. Create Vite project
npm create vite@latest dashboard -- --template react-ts

# 2. Install dependencies
cd dashboard
npm install lightweight-charts @tanstack/react-query zustand axios

# 3. Configure API URL
echo "VITE_API_URL=http://192.168.1.100:8000" > .env.local

# 4. Run dev server
npm run dev

# 5. Build for production
npm run build

# 6. Deploy to Vercel
vercel --prod
```

### Tailscale VPN

```bash
# 1. Install Tailscale
# Download from tailscale.com

# 2. Sign in and connect devices

# 3. Get Tailscale IP
tailscale ip

# 4. Update .env with Tailscale IP
API_HOST=100.x.x.x

# 5. Access from anywhere
# http://100.x.x.x:3000
```

---

## Security Recommendations

### For Local Network Only
- ✅ Bind to local IP only (not 0.0.0.0)
- ✅ Configure Windows Firewall (block public)
- ✅ Use strong passwords + 2FA
- ✅ Keep services updated

### For SPA Deployment
- ✅ **MUST use HTTPS** for API
- ✅ Implement rate limiting
- ✅ Use JWT with short expiry
- ✅ Require 2FA for sensitive operations
- ✅ Monitor access logs
- ✅ Consider API key authentication

### For VPN
- ✅ Use Tailscale ACLs (access control lists)
- ✅ Enable 2FA on Tailscale account
- ✅ Regularly rotate JWT secrets
- ✅ Monitor Tailscale logs

---

## Recommended Approach

### For Your Use Case (Local Desktop Server)

**I recommend: Option 1 (Local Network Only)**

**Why:**
1. ✅ Your server is on an old desktop (local)
2. ✅ Maximum security (no internet exposure)
3. ✅ Simplest setup
4. ✅ Fast (local network)

**If you need remote access later:**
- Add Tailscale VPN (Option 3) - takes 5 minutes
- Or convert to SPA (Option 2) if you want public access

---

## Migration Path

```
Start: Local Network Only
  │
  ├─ Need remote access? → Add Tailscale VPN
  │
  └─ Want public access? → Convert to SPA + Expose API
```

---

## Questions?

- **Q: Can I use both local and VPN?**  
  A: Yes! Bind to `0.0.0.0` and use firewall rules to allow both.

- **Q: Can I use Vite instead of Next.js?**  
  A: Yes! Vite is actually simpler for SPAs. See Option 2.

- **Q: Do I need HTTPS for local network?**  
  A: Not required, but recommended. Self-signed cert is fine.

- **Q: Can I deploy SPA without exposing API?**  
  A: No. SPA needs to call API, so API must be accessible. Use VPN or expose with HTTPS.

---

*Last updated: December 31, 2024*
