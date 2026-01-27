"""
Credential Manager for MT5 password encryption/decryption
Uses Fernet symmetric encryption for secure credential storage
"""

import os
import hashlib
import base64
from cryptography.fernet import Fernet
from utils.logging_config import get_logger


class CredentialManager:
    """Manages encryption/decryption of MT5 credentials"""

    def __init__(self):
        """
        Initialize CredentialManager with encryption key from environment
        
        :raises ValueError: If MT5_ENCRYPTION_KEY is not set
        """
        key = os.getenv("MT5_ENCRYPTION_KEY")
        if not key:
            raise ValueError("MT5_ENCRYPTION_KEY environment variable required")
        
        self.logger = get_logger("credential_manager", "credential_manager.log")
        
        # Support both base64-encoded key or generate from string
        try:
            # Try to use key directly as Fernet key
            self.cipher = Fernet(key.encode())
        except Exception:
            # If key is not valid Fernet key, derive from it
            self.logger.info("Deriving Fernet key from MT5_ENCRYPTION_KEY")
            key_bytes = key.encode()
            key_hash = hashlib.sha256(key_bytes).digest()
            fernet_key = base64.urlsafe_b64encode(key_hash)
            self.cipher = Fernet(fernet_key)

    def encrypt_password(self, password: str) -> bytes:
        """
        Encrypt a password
        
        :param password: Plain text password
        :return: Encrypted password as bytes
        """
        try:
            return self.cipher.encrypt(password.encode())
        except Exception as e:
            self.logger.error(f"Failed to encrypt password: {e}", exc_info=True)
            raise

    def decrypt_password(self, encrypted: bytes) -> str:
        """
        Decrypt an encrypted password
        
        :param encrypted: Encrypted password as bytes
        :return: Plain text password
        :raises ValueError: If decryption fails
        """
        try:
            return self.cipher.decrypt(encrypted).decode()
        except Exception as e:
            self.logger.error(f"Failed to decrypt password: {e}", exc_info=True)
            raise ValueError(f"Failed to decrypt password: {e}")
