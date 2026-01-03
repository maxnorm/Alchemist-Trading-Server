"""
Data Provider Registry

Manages registration and discovery of data providers.
Enables auto-discovery of features from all registered providers.
"""

import logging
import threading
from typing import Dict, List, Optional
from data_providers.base_provider import DataProvider, Feature

logger = logging.getLogger(__name__)


class DataProviderRegistry:
    """
    Registry for managing data providers and feature discovery.

    Thread-safe registry that allows providers to be registered,
    and automatically discovers features from all registered providers.
    """

    def __init__(self):
        """Initialize the registry with thread-safe storage."""
        self._providers: Dict[str, DataProvider] = {}
        self._lock = threading.Lock()
        self._metadata: Dict[str, Dict] = (
            {}
        )  # Provider metadata (version, description, etc.)

    def register_provider(
        self, name: str, provider: DataProvider, metadata: Optional[Dict] = None
    ) -> None:
        """
        Register a data provider instance.

        :param name: Unique name for the provider
        :param provider: DataProvider instance
        :param metadata: Optional metadata dict (version, description, etc.)
        :raises ValueError: If name is empty or provider is None
        """
        if not name:
            raise ValueError("Provider name cannot be empty")
        if provider is None:
            raise ValueError("Provider cannot be None")

        with self._lock:
            if name in self._providers:
                logger.warning(f"Provider '{name}' already registered, overwriting")
            self._providers[name] = provider
            if metadata:
                self._metadata[name] = metadata
            logger.info(f"Registered provider: {name}")

    def discover_features(self) -> List[Feature]:
        """
        Discover features from all registered providers.

        Iterates through all registered providers and extracts their
        declared features. Handles errors gracefully - if a provider
        fails to return features, it logs a warning and continues.

        :return: List of all discovered features
        """
        all_features = []

        with self._lock:
            providers_copy = dict(self._providers)

        for name, provider in providers_copy.items():
            try:
                features = provider.get_features()
                if not isinstance(features, list):
                    logger.warning(
                        f"Provider '{name}' returned non-list from get_features()"
                    )
                    continue

                for feature in features:
                    if not isinstance(feature, Feature):
                        logger.warning(
                            f"Provider '{name}' returned non-Feature object: {type(feature)}"
                        )
                        continue
                    all_features.append(feature)

                logger.debug(
                    f"Discovered {len(features)} features from provider '{name}'"
                )
            except Exception as e:
                logger.error(
                    f"Error discovering features from provider '{name}': {e}",
                    exc_info=True,
                )

        logger.info(
            f"Discovered {len(all_features)} total features from {len(providers_copy)} providers"
        )
        return all_features

    def get_provider(self, name: str) -> Optional[DataProvider]:
        """
        Retrieve a provider by name.

        :param name: Provider name
        :return: DataProvider instance or None if not found
        """
        with self._lock:
            return self._providers.get(name)

    def get_all_providers(self) -> Dict[str, DataProvider]:
        """
        Get all registered providers.

        :return: Dictionary mapping provider names to instances
        """
        with self._lock:
            return dict(self._providers)

    def check_health(self) -> Dict[str, bool]:
        """
        Check health status of all providers.

        For providers that implement is_stale() method, checks if data is stale.
        For other providers, assumes healthy if they exist.

        :return: Dictionary mapping provider names to health status (True = healthy)
        """
        health_status = {}

        with self._lock:
            providers_copy = dict(self._providers)

        for name, provider in providers_copy.items():
            try:
                if hasattr(provider, "is_stale"):
                    # Check if data is stale (not older than 60 seconds by default)
                    is_stale = provider.is_stale(max_age_seconds=60.0)
                    health_status[name] = not is_stale
                else:
                    # Provider exists but doesn't have is_stale method - assume healthy
                    health_status[name] = True
            except Exception as e:
                logger.error(
                    f"Error checking health for provider '{name}': {e}", exc_info=True
                )
                health_status[name] = False

        return health_status

    def unregister_provider(self, name: str) -> None:
        """
        Unregister a provider.

        :param name: Provider name to remove
        """
        with self._lock:
            if name in self._providers:
                del self._providers[name]
                if name in self._metadata:
                    del self._metadata[name]
                logger.info(f"Unregistered provider: {name}")
            else:
                logger.warning(f"Attempted to unregister non-existent provider: {name}")

    def get_provider_count(self) -> int:
        """
        Get the number of registered providers.

        :return: Number of registered providers
        """
        with self._lock:
            return len(self._providers)

    def get_provider_metadata(self, name: str) -> Optional[Dict]:
        """
        Get metadata for a provider.

        :param name: Provider name
        :return: Metadata dict or None if not found
        """
        with self._lock:
            return self._metadata.get(name)
