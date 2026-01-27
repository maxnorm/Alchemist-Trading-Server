"""
Clerk integration service for authentication and authorization
"""

from typing import Optional, Dict, Any, List
from clerk_backend_api import Clerk
from clerk_backend_api.security.types import AuthenticateRequestOptions
import httpx
import logging

from config import settings

logger = logging.getLogger(__name__)


class ClerkService:
    """Service for interacting with Clerk"""

    def __init__(self):
        self._clerk: Optional[Clerk] = None

    def _ensure_initialized(self) -> None:
        """Ensure Clerk SDK is initialized, raise error if CLERK_SECRET_KEY is not set"""
        if self._clerk is None:
            if not settings.clerk_secret_key:
                raise ValueError(
                    "CLERK_SECRET_KEY is not configured. "
                    "Please set CLERK_SECRET_KEY environment variable to use authentication."
                )
            self._clerk = Clerk(bearer_auth=settings.clerk_secret_key)

    @property
    def clerk(self) -> Clerk:
        """Get Clerk instance, initializing if necessary"""
        self._ensure_initialized()
        assert self._clerk is not None, "Clerk should be initialized after _ensure_initialized()"
        return self._clerk

    def verify_request(self, request: httpx.Request) -> Dict[str, Any]:
        """
        Verify Clerk request using authenticate_request method (recommended approach)

        Args:
            request: httpx.Request object with Authorization header

        Returns:
            Dictionary with session information including user_id and payload

        Raises:
            ValueError: If request is not authenticated
        """
        try:
            request_state = self.clerk.authenticate_request(
                request, AuthenticateRequestOptions()
            )

            if not request_state.is_signed_in:
                reason = getattr(request_state, "reason", "Authentication failed")
                raise ValueError(f"Request not authenticated: {reason}")

            # Extract user information from payload
            payload = request_state.payload
            if not payload:
                raise ValueError("No payload in authenticated request")

            # Extract user_id from payload (sub claim in JWT)
            user_id = payload.get("sub") or payload.get("user_id")
            if not user_id:
                raise ValueError("No user_id found in token payload")

            return {
                "user_id": user_id,
                "payload": payload,
            }
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Request authentication failed: {e}")
            raise ValueError(f"Invalid request: {str(e)}")

    def verify_token(self, token: str) -> Dict[str, Any]:
        """
        Verify Clerk session token and return session info
        This method creates a mock request for authenticate_request

        Args:
            token: Clerk session token (JWT)

        Returns:
            Dictionary with session information including user_id

        Raises:
            ValueError: If token is invalid or expired
        """
        try:
            request = httpx.Request(
                method="GET",
                url="https://api.example.com",
                headers={"Authorization": f"Bearer {token}"},
            )
            return self.verify_request(request)
        except Exception as e:
            logger.error(f"Token verification failed: {e}")
            raise ValueError(f"Invalid token: {str(e)}")

    def get_user(self, user_id: str) -> Dict[str, Any]:
        """
        Get user information from Clerk

        Args:
            user_id: Clerk user ID

        Returns:
            Dictionary with user information including roles
        """
        try:
            # Use get() method with keyword argument for Clerk SDK v4.2.0+
            # The get() method requires user_id to be passed as a keyword argument
            user = self.clerk.users.get(user_id=user_id)

            # Extract roles from public metadata or organization memberships
            roles: List[str] = []
            if hasattr(user, "public_metadata") and user.public_metadata:
                if isinstance(user.public_metadata, dict):
                    metadata_roles = user.public_metadata.get("roles", [])
                    if isinstance(metadata_roles, list):
                        roles.extend(metadata_roles)

            # Also check organization memberships for roles
            if (
                hasattr(user, "organization_memberships")
                and user.organization_memberships
            ):
                for membership in user.organization_memberships:
                    if hasattr(membership, "role") and membership.role:
                        roles.append(membership.role)

            return {
                "id": user.id,
                "email": (
                    user.email_addresses[0].email_address
                    if user.email_addresses
                    else None
                ),
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "roles": list(set(roles)),
            }
        except Exception as e:
            logger.error(f"Failed to get user: {e}")
            raise

    def extract_roles(self, user_data: Dict[str, Any]) -> List[str]:
        """Extract roles from user data"""
        return user_data.get("roles", [])


clerk_service = ClerkService()
