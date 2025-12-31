# Vite/React SPA Setup Guide

**Convert dashboard to a standalone SPA that can be deployed to Vercel/Netlify.**

---

## Why Vite Instead of Next.js?

| Feature | Next.js | Vite |
|---------|---------|------|
| **Build Output** | Server + Static | Pure Static |
| **Deployment** | Requires Node.js | Static files only |
| **Bundle Size** | Larger | Smaller |
| **Dev Speed** | Fast | Faster |
| **Best For** | SSR/SSG | SPA |

**For a trading dashboard SPA, Vite is simpler!**

---

## Step 1: Create Vite Project

```bash
# Create new Vite project
npm create vite@latest dashboard-spa -- --template react-ts

cd dashboard-spa
npm install
```

---

## Step 2: Install Dependencies

```bash
# Core dependencies
npm install lightweight-charts @tanstack/react-query zustand axios date-fns

# UI components
npm install lucide-react class-variance-authority clsx tailwind-merge

# Tailwind CSS
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

---

## Step 3: Configure Tailwind

**`tailwind.config.js`:**
```js
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          primary: '#0a0e14',
          secondary: '#151a21',
          tertiary: '#1c232d',
        },
        accent: {
          profit: '#00d26a',
          loss: '#ff4757',
          buy: '#2196f3',
          sell: '#ff9800',
        },
      },
    },
  },
  plugins: [],
}
```

**`src/index.css`:**
```css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  @apply bg-primary text-white;
}
```

---

## Step 4: Configure API Client

**`src/lib/api.ts`:**
```typescript
import axios from 'axios';

// API URL from environment (or default to local)
const API_URL = import.meta.env.VITE_API_URL || 'http://192.168.1.100:8000';

export const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle auth errors
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Redirect to login
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);
```

---

## Step 5: Environment Variables

**`.env.local` (development):**
```env
VITE_API_URL=http://192.168.1.100:8000
VITE_WS_URL=ws://192.168.1.100:8000
```

**`.env.production` (production):**
```env
VITE_API_URL=https://api.yourdomain.com
VITE_WS_URL=wss://api.yourdomain.com
```

**Important:** Vite requires `VITE_` prefix for env variables!

---

## Step 6: WebSocket Hook

**`src/hooks/useWebSocket.ts`:**
```typescript
import { useEffect, useState, useRef } from 'react';

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://192.168.1.100:8000';

export function useWebSocket(endpoint: string) {
  const [data, setData] = useState<any>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();

  useEffect(() => {
    const connect = () => {
      const token = localStorage.getItem('auth_token');
      const ws = new WebSocket(`${WS_URL}${endpoint}?token=${token}`);

      ws.onopen = () => {
        setConnected(true);
        console.log('WebSocket connected');
      };

      ws.onmessage = (event) => {
        setData(JSON.parse(event.data));
      };

      ws.onclose = () => {
        setConnected(false);
        // Auto-reconnect after 3 seconds
        reconnectTimeoutRef.current = setTimeout(connect, 3000);
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
      };

      wsRef.current = ws;
    };

    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      wsRef.current?.close();
    };
  }, [endpoint]);

  return { data, connected };
}
```

---

## Step 7: Router Setup

**`src/App.tsx`:**
```typescript
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Login } from './pages/Login';
import { Dashboard } from './pages/Dashboard';
import { useAuthStore } from './stores/authStore';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { token } = useAuthStore();
  return token ? <>{children}</> : <Navigate to="/login" />;
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
```

**Install React Router:**
```bash
npm install react-router-dom
```

---

## Step 8: Build Configuration

**`vite.config.ts`:**
```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
  server: {
    host: '0.0.0.0', // Allow access from network
    port: 3000,
  },
});
```

---

## Step 9: Build & Deploy

### Build for Production

```bash
npm run build
# Output: dist/ folder with static files
```

### Deploy to Vercel

```bash
# Install Vercel CLI
npm install -g vercel

# Deploy
vercel --prod

# Or connect GitHub repo for auto-deploy
```

### Deploy to Netlify

```bash
# Install Netlify CLI
npm install -g netlify-cli

# Deploy
netlify deploy --prod --dir=dist
```

### Deploy to GitHub Pages

```bash
# Install gh-pages
npm install -D gh-pages

# Add to package.json
{
  "scripts": {
    "deploy": "npm run build && gh-pages -d dist"
  }
}

# Deploy
npm run deploy
```

---

## Step 10: Expose API (Required for SPA)

**Your FastAPI must be accessible from the internet** (since SPA is hosted elsewhere).

### Option A: Cloudflare Tunnel (Recommended - Free, No Port Forwarding)

```bash
# Install cloudflared
# Windows: Download from GitHub releases

# Create tunnel
cloudflared tunnel create trading-api

# Run tunnel (exposes localhost:8000)
cloudflared tunnel run trading-api

# Or configure DNS
cloudflared tunnel route dns trading-api api.yourdomain.com
```

### Option B: ngrok (Quick Testing)

```bash
# Install ngrok
# https://ngrok.com/download

# Expose API
ngrok http 8000

# Use the HTTPS URL (e.g., https://abc123.ngrok.io)
```

### Option C: Port Forwarding + Dynamic DNS

1. Forward port 8000 on your router
2. Use DuckDNS or No-IP for dynamic DNS
3. Set up Let's Encrypt SSL certificate

---

## Step 11: Update CORS in FastAPI

**Allow your SPA domain:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://your-dashboard.vercel.app",
        "https://your-dashboard.netlify.app",
        "http://localhost:3000",  # Local dev
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Project Structure

```
dashboard-spa/
├── src/
│   ├── components/
│   │   ├── ui/              # shadcn/ui components
│   │   ├── charts/
│   │   │   └── PriceChart.tsx
│   │   └── dashboard/
│   │       ├── AccountWidget.tsx
│   │       └── AIControlPanel.tsx
│   ├── pages/
│   │   ├── Login.tsx
│   │   └── Dashboard.tsx
│   ├── hooks/
│   │   ├── useWebSocket.ts
│   │   └── useAuth.ts
│   ├── lib/
│   │   ├── api.ts
│   │   └── utils.ts
│   ├── stores/
│   │   └── authStore.ts
│   ├── App.tsx
│   └── main.tsx
├── public/
├── index.html
├── vite.config.ts
├── tailwind.config.js
└── package.json
```

---

## Key Differences from Next.js

| Feature | Next.js | Vite SPA |
|---------|---------|----------|
| **Routing** | File-based (`app/`) | React Router |
| **API Calls** | Server components | Client-side only |
| **Build Output** | `.next/` | `dist/` (static) |
| **Deployment** | Node.js or static export | Static files only |
| **Env Variables** | `NEXT_PUBLIC_*` | `VITE_*` |

---

## Advantages of Vite SPA

✅ **Simpler deployment** - Just static files  
✅ **Faster builds** - Vite is very fast  
✅ **Smaller bundle** - No Next.js runtime  
✅ **Works everywhere** - Any static host  
✅ **Better for SPAs** - Designed for client-side apps  

---

## Migration Checklist

- [ ] Create Vite project
- [ ] Install all dependencies
- [ ] Copy components from Next.js
- [ ] Set up React Router
- [ ] Configure API client
- [ ] Set up WebSocket hooks
- [ ] Update environment variables
- [ ] Build and test locally
- [ ] Deploy to hosting
- [ ] Expose API (Cloudflare/ngrok)
- [ ] Update CORS in FastAPI
- [ ] Test production deployment

---

## Troubleshooting

**Build errors?**
- Check `vite.config.ts` syntax
- Verify all imports are correct
- Check TypeScript errors: `npm run build -- --mode development`

**API connection fails?**
- Verify `VITE_API_URL` is set correctly
- Check CORS settings in FastAPI
- Test API directly: `curl https://your-api.com/api/health`

**WebSocket not connecting?**
- Verify `VITE_WS_URL` uses `wss://` for HTTPS
- Check WebSocket authentication
- Test WebSocket: `wscat -c wss://your-api.com/ws/ticks`

---

*For local-only setup, see `QUICK_START_LOCAL.md`*  
*For all deployment options, see `DEPLOYMENT_OPTIONS.md`*
