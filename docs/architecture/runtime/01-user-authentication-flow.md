# Runtime Scenario: User Authentication Flow

## Purpose
This diagram answers: **How does a user authenticate and access protected resources?**

## Scope
- **Includes**: Sign-in, JWT verification, role extraction, protected route access
- **Excludes**: User registration (handled entirely by Clerk)

## Source of Truth References
| Step | Evidence Path |
|------|---------------|
| Clerk Provider | `src/dashboard/src/App.tsx:97-100` |
| ProtectedRoute | `src/dashboard/src/components/ProtectedRoute.tsx` |
| API Token Injection | `src/dashboard/src/services/api.ts:27-38`, `src/dashboard/src/hooks/useClerkApi.ts` |
| Auth Middleware | `src/api/src/middleware/auth.py:15-72` |
| Clerk Service | `src/api/src/services/clerk_service.py` |

## Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    participant User
    participant Browser
    participant Dashboard as React Dashboard
    participant Clerk as Clerk (External)
    participant API as FastAPI
    participant DB as PostgreSQL

    %% Initial page load
    User->>Browser: Navigate to /dashboard
    Browser->>Dashboard: Load React App
    Dashboard->>Dashboard: Check ClerkProvider.isSignedIn
    
    alt Not Signed In
        Dashboard->>Browser: Redirect to /sign-in
        Browser->>Clerk: Load Clerk Sign-In Component
        User->>Clerk: Enter credentials
        Clerk->>Clerk: Authenticate user
        Clerk->>Browser: Set session cookie + JWT
        Browser->>Dashboard: Redirect to /dashboard
    end

    %% Authenticated request flow
    Dashboard->>Dashboard: ProtectedRoute renders
    Dashboard->>Clerk: getToken()
    Clerk-->>Dashboard: JWT Token
    
    Dashboard->>API: GET /api/experiments<br/>Authorization: Bearer {JWT}
    
    API->>API: CORS Middleware
    API->>API: Metrics Middleware
    API->>API: Auth Middleware (get_current_user)
    
    API->>Clerk: Verify JWT (JWKS)
    Clerk-->>API: Session data (user_id)
    
    API->>Clerk: Get user details
    Clerk-->>API: User data (email, roles)
    
    API->>API: Extract roles from metadata
    API->>API: Set request.state.user_id, roles
    
    API->>DB: Query experiments
    DB-->>API: Experiment data
    
    API-->>Dashboard: 200 OK + JSON response
    Dashboard-->>Browser: Render experiment list
    Browser-->>User: Display UI

    %% Token expiration handling
    Note over Dashboard,API: If token expired...
    Dashboard->>API: Request with expired token
    API->>Clerk: Verify JWT fails
    API-->>Dashboard: 401 Unauthorized
    Dashboard->>Browser: Redirect to /sign-in
```

## Flow Description

### 1. Initial Page Load
1. User navigates to a protected route (e.g., `/dashboard`)
2. React app loads with ClerkProvider wrapping all components
3. ProtectedRoute checks authentication status via `useAuth()` hook

### 2. Sign-In (if not authenticated)
1. User is redirected to `/sign-in` page
2. Clerk's hosted sign-in component handles authentication
3. Credentials are verified by Clerk
4. Session is established with JWT token

### 3. API Request with Authentication
1. Dashboard calls `api.getExperiments()`
2. API client's request interceptor calls Clerk's `getToken()`
3. JWT is added to Authorization header
4. FastAPI receives request through middleware chain:
   - **CORS** → validates origin
   - **Metrics** → records request metrics
   - **Auth** → extracts and verifies JWT

### 4. JWT Verification
1. `get_current_user` dependency extracts Bearer token
2. `clerk_service.verify_token(token)` validates JWT:
   - Fetches JWKS from Clerk
   - Verifies signature and expiration
   - Extracts session claims
3. User details fetched from Clerk API
4. Roles extracted from user metadata

### 5. Authorization
1. User ID and roles stored in `request.state`
2. Route handler can access via dependency injection
3. Role-based access control via `require_roles()` decorator

## Error Scenarios

| Scenario | Response | Client Action |
|----------|----------|---------------|
| No token provided | 401 Unauthorized | Redirect to /sign-in |
| Invalid/expired token | 401 Unauthorized | Redirect to /sign-in |
| Clerk service down | 503 Service Unavailable | Show error message |
| Insufficient roles | 403 Forbidden | Show unauthorized page |

## Assumptions
- **None** - All authentication flows verified in codebase
