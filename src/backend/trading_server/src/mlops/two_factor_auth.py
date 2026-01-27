"""
Two-Factor Authentication Module

TOTP-based 2FA for sensitive operations.
For local deployment, this verifies TOTP tokens sent from the frontend.
"""

import logging
import time
import hmac
import hashlib
import base64
import struct
from typing import Optional

logger = logging.getLogger(__name__)


class TwoFactorAuth:
    """
    TOTP-based 2FA for sensitive operations.

    For local deployment, the frontend manages the TOTP secret (stored in localStorage).
    The backend verifies TOTP tokens sent from the frontend.

    For production, secrets should be stored in the database per user.
    """

    @staticmethod
    def verify_totp(secret: str, token: str, window: int = 1) -> bool:
        """
        Verify a TOTP token against a secret.

        Args:
            secret: TOTP secret (base32 encoded)
            token: TOTP token to verify (6-digit code)
            window: Time window for verification (default: 1, meaning current and previous period)

        Returns:
            True if token is valid
        """
        try:
            # Decode base32 secret
            try:
                secret_bytes = base64.b32decode(
                    secret.upper() + "=" * (8 - len(secret) % 8)
                )
            except Exception as e:
                logger.warning(f"Failed to decode base32 secret: {e}")
                return False

            # Get current time counter
            current_time = int(time.time())
            time_step = 30  # 30 seconds per TOTP period

            # Check current and previous periods (for clock skew tolerance)
            for i in range(-window, window + 1):
                counter = (current_time // time_step) + i

                # Generate TOTP for this counter
                hmac_hash = hmac.new(
                    secret_bytes, struct.pack(">Q", counter), hashlib.sha1
                ).digest()

                # Dynamic truncation
                offset = hmac_hash[19] & 0x0F
                code = (
                    struct.unpack(">I", hmac_hash[offset : offset + 4])[0] & 0x7FFFFFFF
                )
                code = code % 1000000

                # Format as 6-digit string
                generated_token = f"{code:06d}"

                if generated_token == token:
                    return True

            return False

        except Exception as e:
            logger.error(f"Error verifying TOTP: {e}", exc_info=True)
            return False

    @staticmethod
    def require_2fa_for_promotion() -> bool:
        """
        Check if 2FA is required for production promotion.

        Returns:
            True if 2FA is required (always True for production promotions)
        """
        return True

    @staticmethod
    def verify_promotion_token(
        secret: Optional[str], token: str, user_id: Optional[int] = None
    ) -> bool:
        """
        Verify TOTP token for production promotion.

        For local deployment:
        - If secret is provided, verify against it
        - Otherwise, accept any valid-looking token (6 digits) for local dev

        For production:
        - Look up user's TOTP secret from database
        - Verify token against stored secret

        Args:
            secret: Optional TOTP secret (for local deployment)
            token: TOTP token to verify
            user_id: Optional user ID (for database lookup in production)

        Returns:
            True if token is valid
        """
        # Validate token format
        if not token or len(token) != 6 or not token.isdigit():
            logger.warning(f"Invalid TOTP token format: {token}")
            return False

        # For local deployment with secret provided
        if secret:
            return TwoFactorAuth.verify_totp(secret, token)

        # For local deployment without secret (development mode)
        # In production, this should look up the secret from database
        if user_id:
            # TODO: Look up user's TOTP secret from database
            # For now, return False to enforce 2FA
            logger.warning(f"User {user_id} TOTP secret not found in database")
            return False

        # Development mode: accept any 6-digit code
        # WARNING: This should be disabled in production!
        logger.warning(
            "2FA verification in development mode - accepting any 6-digit code"
        )
        return True
