"""
API Version Management

This module provides utilities for managing multiple API versions.
Currently supports v1, with structure ready for future versions (v2, v3, etc.).
"""

from typing import Dict, List, Optional
from fastapi import APIRouter
from config import settings


class APIVersionManager:
    """
    Manages multiple API versions for the FastAPI application.
    
    This class provides a foundation for supporting multiple API versions
    simultaneously (e.g., v1, v2, v3) without requiring major refactoring.
    """

    def __init__(self):
        """Initialize the version manager"""
        self.versions: Dict[str, List[APIRouter]] = {}
        self.default_version = settings.api_version

    def register_version(self, version: str, routers: List[APIRouter]) -> None:
        """
        Register routers for a specific API version.
        
        Args:
            version: API version string (e.g., 'v1', 'v2')
            routers: List of APIRouter instances for this version
        """
        self.versions[version] = routers

    def get_routers(self, version: Optional[str] = None) -> List[APIRouter]:
        """
        Get routers for a specific version.
        
        Args:
            version: API version string. Defaults to settings.api_version.
        
        Returns:
            List of routers for the specified version, or empty list if not found.
        """
        if version is None:
            version = self.default_version
        return self.versions.get(version, [])

    def get_available_versions(self) -> List[str]:
        """
        Get list of all registered API versions.
        
        Returns:
            List of version strings (e.g., ['v1', 'v2'])
        """
        return list(self.versions.keys())

    def is_version_supported(self, version: str) -> bool:
        """
        Check if a specific API version is supported.
        
        Args:
            version: API version string to check
        
        Returns:
            True if version is registered, False otherwise
        """
        return version in self.versions


# Global version manager instance
version_manager = APIVersionManager()

# Version constants
CURRENT_API_VERSION = settings.api_version
API_BASE_PATH = settings.api_base_path
