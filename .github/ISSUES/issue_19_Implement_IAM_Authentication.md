Implement IAM Authentication for Dashboard and API Endpoints

<!-- This issue will be created in repo maxnorm/Alchemist-AI (https://github.com/maxnorm/Alchemist-AI). Changing this line has no effect. -->

Assignees: 
Labels: security, mvp-blocker, api, dashboard, P0
Milestone: Phase 1 - Foundation
Projects: 


<!-- Edit the body of your new issue then click the ✓ "Create Issue" button in the top right of the editor. The first line will be the issue title. Assignees and Labels follow after a blank line. Leave an empty line before beginning the body of the issue. -->

---

## Issue #19: Implement IAM Authentication for Dashboard and API Endpoints

## Problem Statement

Currently, the system has no authentication or authorization:
- **API Endpoints**: All endpoints are publicly accessible without authentication
- **Dashboard**: Placeholder auth token code exists (`src/dashboard/src/services/api.ts:29`) but no actual authentication system
- **WebSocket Connections**: No authentication for WebSocket connections
- **Role-Based Access**: No role-based access control (RBAC) for different user types

This creates security risks:
- Unauthorized access to trading operations
- No audit trail for user actions
- No protection for sensitive endpoints (model assignment, trading control)
- Compliance issues for production deployment

The PRD mentions JWT + 2FA for sensitive operations (`docs/PRD_COMPLETE.md:1478`), but this is not implemented.

## Proposed Solution

**Strategy**: Integrate with **Clerk** as the IAM (Identity and Access Management) service to delegate authentication and user management, reducing development and maintenance burden.

### Why Clerk?

**Clerk** is a frontend-centric authentication platform designed for React, Next.js, and other JavaScript frameworks. It offers pre-built UI components and APIs for managing sessions, multi-factor authentication (MFA), and user profiles.

**Key Benefits:**
- ✅ **Rapid Integration**: Pre-built React components for quick frontend integration
- ✅ **Developer Experience**: Excellent TypeScript support, minimal boilerplate
- ✅ **Modern Features**: Organization-based auth, multi-session management, MFA
- ✅ **Free Tier**: 10,000 Monthly Active Users (MAUs) free
- ✅ **Cost-Effective**: $20/month + $0.02/MAU beyond 10,000
- ✅ **Quick Setup**: Can be integrated in hours rather than days
- ✅ **UI Components**: Pre-built, customizable authentication UI
- ✅ **Documentation**: Excellent developer documentation

**Free Tier:**
- 10,000 Monthly Active Users (MAUs)
- All essential features included
- Pro plan: $20/month + $0.02/MAU beyond 10,000

**Considerations:**
- ⚠️ **React-Centric**: Primarily designed for React/Next.js ecosystems (perfect for our dashboard)
- ⚠️ **Backend Integration**: Requires JWT token verification on FastAPI backend
- ⚠️ **Vendor Lock-in**: Managed service (but standard JWT tokens allow migration if needed)

---

## Integration Plan

### 1. **Clerk Account Setup**

1. **Create Clerk Account:**
   - Sign up at [clerk.com](https://clerk.com/)
   - Create a new application
   - Note down API keys:
     - Frontend API key (for React dashboard)
     - Backend API key (for FastAPI verification)

2. **Configure Clerk Application:**
   - Set allowed redirect URLs:
     - Development: `http://localhost`, `http://localhost:5173`
     - Production: Your production domain
   - Configure sign-up/sign-in methods (email, social, etc.)
   - Set up roles:
     - `admin` - Full system access
     - `trader` - Trading operations and model deployment
     - `researcher` - Experiment creation and model training
     - `viewer` - Read-only access
   - Enable MFA/2FA for sensitive operations (per PRD requirement)

### 2. **Backend Integration (FastAPI)**

#### 2.1 Install Dependencies

Add to `src/api/requirements.txt`:
```txt
clerk-sdk-python>=1.0.0
python-jose[cryptography]>=3.3.0
```

#### 2.2 Configuration

Update `src/api/src/config.py`:
```python
class Settings(BaseSettings):
    # ... existing settings ...
    
    # Clerk Configuration
    clerk_secret_key: str = Field(..., alias="CLERK_SECRET_KEY")
    clerk_publishable_key: Optional[str] = Field(None, alias="CLERK_PUBLISHABLE_KEY")
    
    # JWT Configuration (Clerk uses JWTs)
    clerk_jwks_url: Optional[str] = None
    
    @property
    def get_clerk_jwks_url(self) -> str:
        """Get JWKS URL for Clerk token validation"""
        if self.clerk_jwks_url:
            return self.clerk_jwks_url
        # Extract instance from secret key format: sk_live_xxx or sk_test_xxx
        # JWKS URL format: https://{instance}.clerk.accounts.dev/.well-known/jwks.json
        # For now, we'll use Clerk SDK which handles this automatically
        return ""
```

#### 2.3 Clerk Service

Create `src/api/src/services/clerk_service.py`:
```python
"""
Clerk integration service for authentication and authorization
"""
from typing import Optional, Dict, Any, List
from clerk_sdk_python import Clerk
from clerk_sdk_python.api_client import ApiClient
import logging

from config import settings

logger = logging.getLogger(__name__)


class ClerkService:
    """Service for interacting with Clerk"""
    
    def __init__(self):
        self.clerk = Clerk(bearer_auth=settings.clerk_secret_key)
        self.client = ApiClient(bearer_auth=settings.clerk_secret_key)
    
    async def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify Clerk session token and return user info"""
        try:
            # Use Clerk SDK to verify token
            # Clerk tokens are JWTs that can be verified
            session = self.clerk.sessions.verify_token(token)
            return {
                "user_id": session.user_id,
                "session_id": session.id,
                "expires_at": session.expire_at,
            }
        except Exception as e:
            logger.error(f"Token verification failed: {e}")
            raise
    
    async def get_user(self, user_id: str) -> Dict[str, Any]:
        """Get user information from Clerk"""
        try:
            user = self.clerk.users.get(user_id)
            return {
                "id": user.id,
                "email": user.email_addresses[0].email_address if user.email_addresses else None,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "roles": [org.role for org in user.organization_memberships] if hasattr(user, 'organization_memberships') else [],
            }
        except Exception as e:
            logger.error(f"Failed to get user: {e}")
            raise
    
    def extract_roles(self, user_data: Dict[str, Any]) -> List[str]:
        """Extract roles from user data"""
        return user_data.get("roles", [])


# Global instance
clerk_service = ClerkService()
```

#### 2.4 Authentication Middleware

Create `src/api/src/middleware/auth.py`:
```python
"""
Authentication middleware for FastAPI using Clerk
"""
from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List
import logging

from services.clerk_service import clerk_service

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


async def get_current_user(request: Request, credentials: Optional[HTTPAuthorizationCredentials] = None):
    """Get current authenticated user from Clerk token"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    
    try:
        # Verify token with Clerk
        session_data = await clerk_service.verify_token(token)
        user_id = session_data["user_id"]
        
        # Get user info
        user_data = await clerk_service.get_user(user_id)
        roles = clerk_service.extract_roles(user_data)
        
        # Store in request state
        request.state.user_id = user_id
        request.state.user_email = user_data.get("email")
        request.state.user_username = user_data.get("username")
        request.state.roles = roles
        
        return user_data
    except Exception as e:
        logger.warning(f"Authentication failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_roles(*allowed_roles: str):
    """Dependency to require specific roles"""
    async def role_checker(
        request: Request,
        user: dict = Depends(get_current_user)
    ):
        user_roles = request.state.roles
        if not any(role in user_roles for role in allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required roles: {', '.join(allowed_roles)}"
            )
        return user
    return role_checker
```

#### 2.5 Protect Endpoints

Update routers to use authentication:

**Example: `src/api/src/routers/trading.py`**
```python
from fastapi import APIRouter, Depends, HTTPException
from middleware.auth import get_current_user, require_roles

router = APIRouter()

@router.get("/trading/status")
async def get_trading_status(
    user: dict = Depends(get_current_user),  # Requires authentication
    db: Session = Depends(get_db),
):
    """Get trading status - requires authentication"""
    # user dict contains user info from Clerk
    # request.state.roles contains user roles
    return trading_service.get_trading_status(db)

@router.post("/trading/kill-switch/trigger")
async def trigger_kill_switch(
    user: dict = Depends(require_roles("admin", "trader")),  # Requires role
    # ... existing parameters ...
):
    """Trigger kill switch - requires admin or trader role"""
    # ... existing logic ...
```

**Protected Endpoints:**
- `trading.router` - All endpoints require `trader` or `admin` role
- `mt5_accounts.router` - Model assignment requires `admin` role
- `experiments.router` - Create/update requires `researcher` or `admin` role
- `models.router` - Deployment requires `trader` or `admin` role
- Read-only endpoints (GET) - Require `viewer` role or above

#### 2.6 WebSocket Authentication

Update `src/api/src/websocket/manager.py`:
```python
from services.clerk_service import clerk_service

async def handle_websocket(websocket: WebSocket, channel: str):
    """Handle WebSocket connection with Clerk authentication"""
    await websocket.accept()
    
    # Get token from query params
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008, reason="Authentication required")
        return
    
    try:
        # Verify token with Clerk
        session_data = await clerk_service.verify_token(token)
        user_id = session_data["user_id"]
        user_data = await clerk_service.get_user(user_id)
        
        # Store user info in connection
        websocket.state.user_id = user_id
        websocket.state.roles = clerk_service.extract_roles(user_data)
        
        # ... existing subscription logic ...
    except Exception as e:
        logger.warning(f"WebSocket authentication failed: {e}")
        await websocket.close(code=1008, reason="Invalid token")
        return
```

### 3. **Frontend Integration (React)**

#### 3.1 Install Dependencies

Add to `src/dashboard/package.json`:
```json
{
  "dependencies": {
    "@clerk/clerk-react": "^5.0.0"
  }
}
```

#### 3.2 Environment Variables

Add to `src/dashboard/.env.example`:
```bash
VITE_CLERK_PUBLISHABLE_KEY=pk_test_...
```

#### 3.3 Clerk Configuration

Create `src/dashboard/src/config/clerk.ts`:
```typescript
export const clerkConfig = {
  publishableKey: import.meta.env.VITE_CLERK_PUBLISHABLE_KEY || '',
}
```

#### 3.4 Update App.tsx

Update `src/dashboard/src/App.tsx`:
```typescript
import { ClerkProvider } from '@clerk/clerk-react'
import { clerkConfig } from '@/config/clerk'

function App() {
  return (
    <ClerkProvider publishableKey={clerkConfig.publishableKey}>
      <ErrorBoundary>
        <QueryClientProvider client={queryClient}>
          <UIContextProvider>
            <WebSocketProvider>
              <BrowserRouter>
                <Routes>
                  <Route path="/sign-in/*" element={<SignIn />} />
                  <Route path="/sign-up/*" element={<SignUp />} />
                  <Route path="/" element={<Layout />}>
                    {/* Protected routes */}
                    <Route index element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
                    <Route path="trading" element={<ProtectedRoute requiredRoles={['trader', 'admin']}><LiveTrading /></ProtectedRoute>} />
                    {/* ... other routes ... */}
                  </Route>
                </Routes>
              </BrowserRouter>
            </WebSocketProvider>
          </UIContextProvider>
        </QueryClientProvider>
      </ErrorBoundary>
    </ClerkProvider>
  )
}
```

#### 3.5 Protected Route Component

Create `src/dashboard/src/components/ProtectedRoute.tsx`:
```typescript
import { Navigate } from 'react-router-dom'
import { useAuth, useUser } from '@clerk/clerk-react'

interface ProtectedRouteProps {
  children: React.ReactNode
  requiredRoles?: string[]
}

export function ProtectedRoute({ children, requiredRoles }: ProtectedRouteProps) {
  const { isSignedIn, isLoaded } = useAuth()
  const { user } = useUser()

  if (!isLoaded) {
    return <div>Loading...</div>
  }

  if (!isSignedIn) {
    return <Navigate to="/sign-in" replace />
  }

  if (requiredRoles && user) {
    const userRoles = user.publicMetadata?.roles as string[] || []
    const hasRole = requiredRoles.some((role) => userRoles.includes(role))
    if (!hasRole) {
      return <Navigate to="/unauthorized" replace />
    }
  }

  return <>{children}</>
}
```

#### 3.6 Update API Client

Update `src/dashboard/src/services/api.ts`:
```typescript
import { useAuth } from '@clerk/clerk-react'

// In ApiClient constructor, update interceptor:
this.client.interceptors.request.use(
  async (config) => {
    // Get token from Clerk
    const { getToken } = useAuth()
    const token = await getToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Handle 401 responses
this.client.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    if (error.response?.status === 401) {
      // Token expired, Clerk will handle refresh automatically
      // Redirect to sign-in if refresh fails
      window.location.href = '/sign-in'
    }
    return Promise.reject(error)
  }
)
```

#### 3.7 Update WebSocket Service

Update `src/dashboard/src/services/websocket.ts`:
```typescript
import { useAuth } from '@clerk/clerk-react'

class WebSocketService {
  async connect(): Promise<void> {
    // Get token from Clerk
    const { getToken } = useAuth()
    const token = await getToken()
    
    if (!token) {
      console.error('No authentication token available')
      return
    }

    // Include token in WebSocket URL
    const wsUrl = `${WS_BASE_URL}?token=${encodeURIComponent(token)}`
    this.ws = new WebSocket(wsUrl)
    
    // ... rest of connection logic ...
  }
}
```

#### 3.8 Update Layout/Header

Update `src/dashboard/src/components/Layout/Header.tsx` to show user info and logout:
```typescript
import { UserButton, useUser } from '@clerk/clerk-react'

export function Header() {
  const { user } = useUser()
  
  return (
    <header>
      {/* ... existing header content ... */}
      <div className="user-section">
        {user && (
          <>
            <span>{user.emailAddresses[0]?.emailAddress}</span>
            <UserButton />
          </>
        )}
      </div>
    </header>
  )
}
```

### 4. **Environment Variables**

#### 4.1 Backend (.env)
```bash
# Clerk Configuration
CLERK_SECRET_KEY=sk_test_...  # From Clerk dashboard
CLERK_PUBLISHABLE_KEY=pk_test_...  # Optional, for reference
```

#### 4.2 Frontend (.env)
```bash
VITE_CLERK_PUBLISHABLE_KEY=pk_test_...  # From Clerk dashboard
```

### 5. **Database Schema (for Audit Trail)**

Create migration script: `src/database/scripts/XX_create_user_audit_table.sql`

```sql
-- User audit trail (sync from Clerk for audit purposes)
CREATE TABLE user_audit (
    id SERIAL PRIMARY KEY,
    clerk_user_id VARCHAR(255) NOT NULL UNIQUE, -- User ID from Clerk
    email VARCHAR(255),
    username VARCHAR(100),
    full_name VARCHAR(255),
    last_login TIMESTAMP,
    last_api_access TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- API access logs (for audit trail)
CREATE TABLE api_access_logs (
    id SERIAL PRIMARY KEY,
    clerk_user_id VARCHAR(255),
    endpoint VARCHAR(255) NOT NULL,
    method VARCHAR(10) NOT NULL,
    status_code INTEGER,
    ip_address VARCHAR(45),
    user_agent TEXT,
    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_access (clerk_user_id, accessed_at),
    INDEX idx_endpoint_access (endpoint, accessed_at)
);
```

### 6. **Testing**

#### 6.1 API Tests

Create `tests/api/test_clerk_integration.py`:
```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

def test_protected_endpoint_without_token(client: TestClient):
    """Test that protected endpoints require authentication"""
    response = client.get("/api/v1/trading/status")
    assert response.status_code == 401

def test_protected_endpoint_with_valid_token(client: TestClient):
    """Test protected endpoint with valid Clerk token"""
    with patch('services.clerk_service.clerk_service.verify_token') as mock_verify:
        mock_verify.return_value = {"user_id": "user_123", "session_id": "sess_123"}
        # ... test with mock token ...
```

#### 6.2 Integration Tests

Create `tests/integration/test_clerk_auth_flow.py`:
- End-to-end authentication flow
- WebSocket authentication with Clerk tokens
- Token expiry and refresh handling
- Role-based access control

### 7. **Documentation**

1. **Create Clerk Integration Guide:**
   - File: `docs/CLERK_INTEGRATION_GUIDE.md`
   - Clerk account setup
   - Configuration steps
   - Role setup in Clerk dashboard
   - Troubleshooting guide

2. **Update API Documentation:**
   - File: `docs/API_REFERENCE.md`
   - Document authentication requirements
   - Document protected endpoints
   - Document role requirements
   - Include example requests with Clerk tokens

3. **Create Security Guide:**
   - File: `docs/SECURITY_GUIDE.md`
   - Clerk setup
   - User management procedures
   - Role assignment procedures
   - MFA/2FA configuration
   - Security best practices

## Implementation Steps

1. **Set Up Clerk Account:**
   - Create Clerk account
   - Create application
   - Configure roles (admin, trader, researcher, viewer)
   - Set up MFA/2FA
   - Get API keys

2. **Backend Integration:**
   - Install Clerk SDK
   - Create Clerk service
   - Implement authentication middleware
   - Protect existing endpoints
   - Update WebSocket authentication

3. **Frontend Integration:**
   - Install Clerk React SDK
   - Wrap app with ClerkProvider
   - Create protected route component
   - Update API client with token management
   - Update WebSocket service
   - Add sign-in/sign-up pages

4. **Testing:**
   - Write Clerk integration tests
   - Write end-to-end authentication flow tests
   - Test role-based access control

5. **Documentation:**
   - Create Clerk integration guide
   - Update API documentation
   - Create/update security guide

## Integration Points Summary

### Backend (FastAPI)
- **Routers to Protect:**
  - `trading.router` - All endpoints
  - `mt5_accounts.router` - Model assignment endpoints
  - `experiments.router` - Create/update endpoints
  - `models.router` - Deployment endpoints
  - `features.router` - Read-only (viewer role)
  - `performance.router` - Read-only (viewer role)
  - `data.router` - Read-only (viewer role)

- **Middleware:**
  - `src/api/src/middleware/auth.py` - Clerk authentication middleware

- **Services:**
  - `src/api/src/services/clerk_service.py` - Clerk integration service

- **WebSocket:**
  - `src/api/src/websocket/manager.py` - Add Clerk token validation

### Frontend (React)
- **Components:**
  - `src/dashboard/src/components/ProtectedRoute.tsx` - Route protection
  - `src/dashboard/src/components/Layout/Header.tsx` - User info display

- **Services:**
  - `src/dashboard/src/services/api.ts` - Add Clerk token to requests
  - `src/dashboard/src/services/websocket.ts` - Add Clerk token to WebSocket

- **Pages:**
  - `src/dashboard/src/pages/SignIn.tsx` - Clerk sign-in component
  - `src/dashboard/src/pages/SignUp.tsx` - Clerk sign-up component

- **App:**
  - `src/dashboard/src/App.tsx` - Wrap with ClerkProvider

## Metadata

- **Effort:** M (5 story points)
- **Dependencies:** Clerk account setup
- **Owner Role:** Backend Developer, Frontend Developer
- **Security Impact:** Critical - Required for production deployment
- **Maintenance:** Low - Delegated to Clerk service
