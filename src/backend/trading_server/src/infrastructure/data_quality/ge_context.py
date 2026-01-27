"""
Great Expectations Data Context Configuration
"""

import logging
from pathlib import Path
from typing import Optional, Any

from great_expectations.data_context import BaseDataContext
from great_expectations.data_context.types.base import DataContextConfig

logger = logging.getLogger(__name__)


class GEDataContext:
    """
    Great Expectations Data Context wrapper

    Manages GE context, expectations store, validations store, and Data Docs
    """

    def __init__(self, context_root_dir: Optional[str] = None):
        """
        Initialize Great Expectations Data Context

        :param context_root_dir: Root directory for GE context (default: ./great_expectations)
        """
        # Determine context root directory
        if context_root_dir is None:
            # Use project root / great_expectations
            project_root = Path(__file__).parent.parent.parent.parent.parent
            context_root_dir = str(project_root / "great_expectations")

        self.context_root_dir = Path(context_root_dir)
        self.context_root_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        (self.context_root_dir / "expectations").mkdir(exist_ok=True)
        (self.context_root_dir / "validations").mkdir(exist_ok=True)
        (self.context_root_dir / "data_docs").mkdir(exist_ok=True)
        (self.context_root_dir / "checkpoints").mkdir(exist_ok=True)

        # Initialize GE context
        self.context = self._create_context()

        logger.info(
            f"Great Expectations context initialized at {self.context_root_dir}"
        )

    def _create_context(self) -> Any:
        """Create Great Expectations Data Context"""
        try:
            # Try to load existing context
            # Note: ge.get_context may not exist in all versions, use BaseDataContext directly
            context = BaseDataContext(project_root_dir=str(self.context_root_dir))
            logger.info("Loaded existing Great Expectations context")
            return context
        except Exception:
            # Create new context
            logger.info("Creating new Great Expectations context")
            data_context_config = DataContextConfig(
                config_version=3.0,
                datasources={},
                stores={
                    "expectations_store": {
                        "class_name": "ExpectationsStore",
                        "store_backend": {
                            "class_name": "TupleFilesystemStoreBackend",
                            "base_directory": str(
                                self.context_root_dir / "expectations"
                            ),
                        },
                    },
                    "validations_store": {
                        "class_name": "ValidationsStore",
                        "store_backend": {
                            "class_name": "TupleFilesystemStoreBackend",
                            "base_directory": str(
                                self.context_root_dir / "validations"
                            ),
                        },
                    },
                    "evaluation_parameter_store": {
                        "class_name": "EvaluationParameterStore",
                    },
                    "checkpoint_store": {
                        "class_name": "CheckpointStore",
                        "store_backend": {
                            "class_name": "TupleFilesystemStoreBackend",
                            "base_directory": str(
                                self.context_root_dir / "checkpoints"
                            ),
                        },
                    },
                },
                expectations_store_name="expectations_store",
                validations_store_name="validations_store",
                evaluation_parameter_store_name="evaluation_parameter_store",
                checkpoint_store_name="checkpoint_store",
                data_docs_sites={
                    "local_site": {
                        "class_name": "SiteBuilder",
                        "show_how_to_buttons": True,
                        "store_backend": {
                            "class_name": "TupleFilesystemStoreBackend",
                            "base_directory": str(
                                self.context_root_dir / "data_docs" / "local_site"
                            ),
                        },
                        "site_index_builder": {
                            "class_name": "DefaultSiteIndexBuilder",
                            "show_cta_footer": True,
                        },
                    }
                },
            )

            context = BaseDataContext(project_config=data_context_config)
            return context

    def get_context(self) -> Any:
        """Get Great Expectations Data Context"""
        return self.context

    def get_expectations_store_path(self) -> Path:
        """Get path to expectations store"""
        return self.context_root_dir / "expectations"

    def get_validations_store_path(self) -> Path:
        """Get path to validations store"""
        return self.context_root_dir / "validations"

    def get_data_docs_path(self) -> Path:
        """Get path to Data Docs"""
        return self.context_root_dir / "data_docs" / "local_site"


# Global GE context instance
_ge_context: Optional[GEDataContext] = None


def get_ge_context(context_root_dir: Optional[str] = None) -> GEDataContext:
    """
    Get or create global Great Expectations context

    :param context_root_dir: Root directory for GE context
    :return: GEDataContext instance
    """
    global _ge_context
    if _ge_context is None:
        _ge_context = GEDataContext(context_root_dir)
    return _ge_context
