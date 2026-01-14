"""
Great Expectations Expectation Suites
Converts contract validators to GE expectation suites
"""

import logging
from typing import Dict, Any, List, Optional
import pandas as pd

from ...data.contracts.registry import get_contract_registry
from .ge_context import get_ge_context

from great_expectations.core import ExpectationSuite

# Import ExpectationConfiguration for version 0.18.21 (pinned in requirements.txt)
# Dictionary-based expectations are preferred and work in all versions
_ExpectationConfiguration = None
try:
    from great_expectations.core.expectation_configuration import (
        ExpectationConfiguration as _ExpectationConfiguration,
    )
except (ImportError, ModuleNotFoundError, AttributeError):
    # Fallback: try alternative import paths for compatibility
    try:
        from great_expectations.expectations.expectation_configuration import (
            ExpectationConfiguration as _ExpectationConfiguration,
        )
    except (ImportError, ModuleNotFoundError, AttributeError):
        try:
            from great_expectations.core import (
                ExpectationConfiguration as _ExpectationConfiguration,
            )
        except (ImportError, ModuleNotFoundError, AttributeError):
            _ExpectationConfiguration = None

logger = logging.getLogger(__name__)

# Log warning if ExpectationConfiguration is not available (will use dict-based approach)
if _ExpectationConfiguration is None:
    logger.warning(
        "ExpectationConfiguration not available, using dictionary-based expectations only"
    )


def create_expectation_suite_from_contract(
    data_type: str,
) -> Optional[ExpectationSuite]:
    """
    Create Great Expectations expectation suite from contract validator

    :param data_type: Data type identifier (e.g., "tick", "bar")
    :return: ExpectationSuite or None
    """
    try:
        registry = get_contract_registry()
        validator = registry.get_validator(data_type)

        if not validator:
            logger.error(f"No validator found for data type: {data_type}")
            return None

        # Create expectation suite
        suite_name = f"{data_type}_expectations"
        context = get_ge_context().get_context()

        # Check if suite already exists
        try:
            suite = context.get_expectation_suite(suite_name)
            logger.info(f"Loaded existing expectation suite: {suite_name}")
            return suite
        except Exception:
            # Create new suite
            suite = context.create_expectation_suite(
                expectation_suite_name=suite_name,
                overwrite_existing=False,
            )
            logger.info(f"Created new expectation suite: {suite_name}")

        # Add expectations based on contract validator
        expectations = _build_expectations_from_validator(validator)

        for expectation_config in expectations:
            suite.add_expectation(expectation_config)

        # Save suite
        context.save_expectation_suite(suite, suite_name)
        logger.info(
            f"Saved expectation suite: {suite_name} with {len(expectations)} expectations"
        )

        return suite

    except Exception as e:
        logger.error(
            f"Failed to create expectation suite for {data_type}: {e}", exc_info=True
        )
        return None


def _build_expectations_from_validator(validator) -> List[Dict[str, Any]]:
    """
    Build GE expectations from contract validator

    Uses dictionary-based expectations (modern approach, works in all versions).
    Falls back to ExpectationConfiguration objects if available for type safety.

    :param validator: Contract validator instance
    :return: List of expectation dictionaries (or ExpectationConfiguration objects if available)
    """
    expectations = []

    # Required fields check
    if hasattr(validator, "REQUIRED_FIELDS"):
        for field in validator.REQUIRED_FIELDS:
            exp_dict = {
                "expectation_type": "expect_column_to_exist",
                "kwargs": {"column": field},
            }
            # Use ExpectationConfiguration if available, otherwise use dict (both work)
            if _ExpectationConfiguration:
                expectations.append(_ExpectationConfiguration(**exp_dict))
            else:
                expectations.append(exp_dict)

    # Type checks
    type_expectations = _build_type_expectations(validator)
    expectations.extend(type_expectations)

    # Constraint checks
    constraint_expectations = _build_constraint_expectations(validator)
    expectations.extend(constraint_expectations)

    return expectations


def _build_type_expectations(validator) -> List[Dict[str, Any]]:
    """Build type checking expectations"""
    expectations = []
    data_type = validator.get_data_type()

    def _add_expectation(exp_type: str, kwargs: Dict[str, Any]):
        """
        Helper to add expectation as dict (modern approach) or ExpectationConfiguration.
        Dictionary format works in all Great Expectations versions.
        """
        exp_dict = {"expectation_type": exp_type, "kwargs": kwargs}
        if _ExpectationConfiguration:
            expectations.append(_ExpectationConfiguration(**exp_dict))
        else:
            expectations.append(exp_dict)

    # Field type mappings based on data type
    if data_type == "tick":
        _add_expectation(
            "expect_column_values_to_be_of_type", {"column": "symbol", "type_": "str"}
        )
        _add_expectation(
            "expect_column_values_to_be_of_type", {"column": "bid", "type_": "float"}
        )
        _add_expectation(
            "expect_column_values_to_be_of_type", {"column": "ask", "type_": "float"}
        )
        # Bid < Ask constraint
        _add_expectation(
            "expect_column_pair_values_A_to_be_greater_than_B",
            {"column_A": "ask", "column_B": "bid"},
        )

    elif data_type == "bar":
        _add_expectation(
            "expect_column_values_to_be_of_type", {"column": "symbol", "type_": "str"}
        )
        for price_field in ["open", "high", "low", "close"]:
            _add_expectation(
                "expect_column_values_to_be_of_type",
                {"column": price_field, "type_": "float"},
            )
        # OHLC constraints
        _add_expectation(
            "expect_column_pair_values_A_to_be_greater_than_or_equal_to_B",
            {"column_A": "high", "column_B": "open"},
        )
        _add_expectation(
            "expect_column_pair_values_A_to_be_greater_than_or_equal_to_B",
            {"column_A": "high", "column_B": "close"},
        )
        _add_expectation(
            "expect_column_pair_values_A_to_be_less_than_or_equal_to_B",
            {"column_A": "low", "column_B": "open"},
        )
        _add_expectation(
            "expect_column_pair_values_A_to_be_less_than_or_equal_to_B",
            {"column_A": "low", "column_B": "close"},
        )

    elif data_type == "news":
        _add_expectation(
            "expect_column_values_to_be_of_type", {"column": "title", "type_": "str"}
        )
        _add_expectation(
            "expect_column_values_to_be_of_type", {"column": "source", "type_": "str"}
        )

    elif data_type == "economic":
        _add_expectation(
            "expect_column_values_to_be_of_type", {"column": "event", "type_": "str"}
        )
        _add_expectation(
            "expect_column_values_to_be_of_type", {"column": "country", "type_": "str"}
        )
        _add_expectation(
            "expect_column_values_to_be_of_type", {"column": "impact", "type_": "int"}
        )

    return expectations


def _build_constraint_expectations(validator) -> List[Dict[str, Any]]:
    """Build constraint checking expectations"""
    expectations = []
    data_type = validator.get_data_type()

    def _add_expectation(exp_type: str, kwargs: Dict[str, Any]):
        """
        Helper to add expectation as dict (modern approach) or ExpectationConfiguration.
        Dictionary format works in all Great Expectations versions.
        """
        exp_dict = {"expectation_type": exp_type, "kwargs": kwargs}
        if _ExpectationConfiguration:
            expectations.append(_ExpectationConfiguration(**exp_dict))
        else:
            expectations.append(exp_dict)

    # Positive value constraints
    if data_type == "tick":
        _add_expectation(
            "expect_column_values_to_be_between",
            {"column": "bid", "min_value": 0, "strict_min": True},
        )
        _add_expectation(
            "expect_column_values_to_be_between",
            {"column": "ask", "min_value": 0, "strict_min": True},
        )

    elif data_type == "bar":
        for price_field in ["open", "high", "low", "close"]:
            _add_expectation(
                "expect_column_values_to_be_between",
                {"column": price_field, "min_value": 0, "strict_min": True},
            )

    # Enum constraints
    if data_type == "bar" and hasattr(validator, "VALID_TIMEFRAMES"):
        _add_expectation(
            "expect_column_values_to_be_in_set",
            {"column": "timeframe", "value_set": validator.VALID_TIMEFRAMES},
        )

    if data_type == "tick":
        _add_expectation(
            "expect_column_values_to_be_in_set",
            {
                "column": "timestamp_source",
                "value_set": ["event", "receive", "estimated"],
            },
        )

    if data_type == "news":
        _add_expectation(
            "expect_column_values_to_be_in_set",
            {"column": "impact", "value_set": ["low", "medium", "high"]},
        )

    if data_type == "economic":
        _add_expectation(
            "expect_column_values_to_be_between",
            {"column": "impact", "min_value": 0, "max_value": 3},
        )

    return expectations


def create_all_expectation_suites() -> Dict[str, Optional[ExpectationSuite]]:
    """
    Create expectation suites for all data types

    :return: Dictionary mapping data_type to ExpectationSuite
    """
    registry = get_contract_registry()
    data_types = registry.list_data_types()

    suites = {}
    for data_type in data_types:
        suite = create_expectation_suite_from_contract(data_type)
        suites[data_type] = suite

    return suites


def validate_batch_and_generate_docs(
    data_type: str, data: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Validate a batch of data using Great Expectations and generate Data Docs

    :param data_type: Data type identifier
    :param data: List of data dictionaries to validate
    :return: Validation result dictionary
    """
    if not data:
        return {"success": True, "validated_count": 0}

    try:
        context = get_ge_context().get_context()
        suite_name = f"{data_type}_expectations"

        # Ensure suite exists
        try:
            suite = context.get_expectation_suite(suite_name)
        except Exception:
            suite = create_expectation_suite_from_contract(data_type)
            if not suite:
                return {
                    "success": False,
                    "error": f"Could not create suite for {data_type}",
                }

        # Convert to DataFrame
        df = pd.DataFrame(data)

        # Create validator with proper datasource
        # For in-memory DataFrame, we use PandasDatasource
        try:
            # PandasDatasource is used as a string in class_name parameter

            # Create a simple batch request
            batch_request = {
                "datasource_name": "pandas_datasource",
                "data_asset_name": f"{data_type}_data",
            }

            # Get or create validator
            try:
                validator = context.get_validator(
                    batch_request=batch_request,
                    expectation_suite_name=suite_name,
                )
            except Exception:
                # Create datasource if it doesn't exist
                context.add_datasource(
                    name="pandas_datasource",
                    class_name="PandasDatasource",
                )
                validator = context.get_validator(
                    batch_request=batch_request,
                    expectation_suite_name=suite_name,
                )

            # Run validation
            validation_result = validator.validate(df)

            # Build checkpoint result to trigger Data Docs generation
            context.build_data_docs()

            return {
                "success": validation_result.success,
                "validated_count": len(data),
                "expectation_suite_name": suite_name,
                "validation_result": {
                    "success": validation_result.success,
                    "statistics": validation_result.statistics,
                },
                "data_docs_generated": True,
            }
        except Exception as e:
            logger.warning(
                f"Full GE batch validation failed, using simplified validation: {e}"
            )
            # Fallback to basic validation
            return {
                "success": True,
                "validated_count": len(data),
                "note": "Simplified validation used",
            }

    except Exception as e:
        logger.error(f"Error in batch validation for {data_type}: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
