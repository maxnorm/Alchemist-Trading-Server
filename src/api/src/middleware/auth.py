"""
Authentication middleware for FastAPI using Clerk
"""
from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict
import logging

from config import settings
from services.clerk_service import clerk_service

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Dict:
    """
    Get current authenticated user from Clerk token

    Usage:
        @router.get("/endpoint")
        async def my_endpoint(user: dict = Depends(get_current_user)):
            # user contains user info
            # request.state.roles contains user roles
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        session_data = clerk_service.verify_token(token)
        user_id = session_data["user_id"]

        # Get user info
        user_data = clerk_service.get_user(user_id)
        roles = clerk_service.extract_roles(user_data)

        # Store in request state for access in route handlers
        request.state.user_id = user_id
        request.state.user_email = user_data.get("email")
        request.state.user_username = user_data.get("username")
        request.state.roles = roles

        return user_data
    except ValueError as e:
        error_message = str(e)
        # Check if the error is about missing CLERK_SECRET_KEY
        if "CLERK_SECRET_KEY" in error_message:
            logger.error(f"Clerk authentication not configured: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service is not configured. Please set CLERK_SECRET_KEY environment variable.",
            )
        logger.warning(f"Authentication failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"Unexpected authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service error",
        )


def require_roles(*allowed_roles: str):
    """
    Dependency factory to require specific roles (kept for future use)

    Currently, all endpoints use get_current_user for authentication.
    This function is available for future role-based access control.

    Usage:
        @router.post("/endpoint")
        async def my_endpoint(user: dict = Depends(require_roles("admin", "user"))):
            # Only users with admin or user role can access
    """
    async def role_checker(
        request: Request,
        user: Dict = Depends(get_current_user),
    ):
        user_roles = request.state.roles
        if not any(role in user_roles for role in allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required roles: {', '.join(allowed_roles)}. Your roles: {', '.join(user_roles)}",
            )
        return user

    return role_checker


def require_account_ownership(account_id_param: str = "account_id"):
    """
    Dependency factory to require account ownership or admin role

    Usage:
        @router.get("/accounts/{account_id}")
        async def get_account(
            account_id: int,
            user: dict = Depends(require_account_ownership()),
            db: Session = Depends(get_db),
        ):
            # Only account owner or admin can access
    """
    async def ownership_checker(
        request: Request,
        user: Dict = Depends(get_current_user),
        db: Session = Depends(lambda: None),  # Will be injected by FastAPI
    ):
        from dependencies import get_db
        from services.mt5_accounts_service import verify_account_ownership

        # Get account_id from path parameters
        account_id = request.path_params.get(account_id_param)
        if not account_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing {account_id_param} parameter",
            )

        try:
            account_id = int(account_id)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid {account_id_param} parameter",
            )

        user_id = user.get("id") or request.state.user_id
        user_roles = request.state.roles

        # Admins can access any account
        if "admin" in user_roles:
            return user

        # Regular users must own the account
        # Get db session from dependencies
        db_gen = get_db()
        db_session = next(db_gen)
        try:
            if not verify_account_ownership(db_session, account_id, user_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied. You do not own this account.",
                )
        finally:
            try:
                next(db_gen, None)  # Cleanup generator
            except StopIteration:
                pass

        return user

    return ownership_checker