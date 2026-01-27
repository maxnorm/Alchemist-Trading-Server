"""
Schema Converter - Converts contract definitions to JSON Schema format
"""

from typing import Dict, Any, List
from ...data.contracts.base import IContractValidator


def contract_to_json_schema(validator: IContractValidator) -> Dict[str, Any]:
    """
    Convert contract validator to JSON Schema Draft 7 format

    :param validator: Contract validator instance
    :return: JSON Schema dictionary
    """
    data_type = validator.get_data_type()
    version = validator.get_contract_version()

    # Get required and optional fields
    required_fields: List[str] = []
    properties: Dict[str, Any] = {}

    # Build properties from validator's field definitions
    # For now, we'll create a basic schema structure
    # This can be enhanced to extract more detailed field definitions

    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "title": f"{data_type} schema v{version}",
        "description": f"Schema for {data_type} data type version {version}",
        "properties": properties,
        "required": required_fields,
        "additionalProperties": False,
    }

    # Add required fields based on validator
    if hasattr(validator, "REQUIRED_FIELDS"):
        required_fields.extend(validator.REQUIRED_FIELDS)

    # Build properties - use basic type inference
    all_fields = []
    if hasattr(validator, "REQUIRED_FIELDS"):
        all_fields.extend(validator.REQUIRED_FIELDS)
    if hasattr(validator, "OPTIONAL_FIELDS"):
        all_fields.extend(validator.OPTIONAL_FIELDS)

    # Map common field types
    for field in all_fields:
        field_schema = _infer_field_schema(field, data_type)
        if field_schema:
            properties[field] = field_schema

    return schema


def _infer_field_schema(field_name: str, data_type: str) -> Dict[str, Any]:
    """
    Infer JSON Schema for a field based on field name and data type

    :param field_name: Field name
    :param data_type: Data type identifier
    :return: Field schema dictionary
    """
    # Common field patterns
    if field_name == "symbol":
        return {
            "type": "string",
            "pattern": "^[A-Z]{6}$",
            "description": "Currency pair symbol (6 uppercase letters)",
        }
    elif field_name in ["datetime", "receive_time"]:
        return {
            "type": "string",
            "format": "date-time",
            "description": "ISO 8601 datetime in UTC",
        }
    elif field_name in ["bid", "ask", "open", "high", "low", "close", "volume"]:
        return {
            "type": "number",
            "minimum": 0,
            "description": f"{field_name} value",
        }
    elif field_name in ["latency_seconds", "stale_age_seconds", "impact"]:
        return {
            "type": "integer",
            "minimum": 0,
            "description": f"{field_name} value",
        }
    elif field_name == "is_stale":
        return {
            "type": "boolean",
            "description": "Whether data is stale",
        }
    elif field_name == "timestamp_source":
        return {
            "type": "string",
            "enum": ["event", "receive", "estimated"],
            "description": "Source of timestamp",
        }
    elif field_name == "timeframe":
        return {
            "type": "string",
            "enum": ["M1", "M5", "M15", "M30", "H1", "H4", "D1"],
            "description": "Timeframe identifier",
        }
    elif field_name in ["title", "content", "source", "event", "country"]:
        return {
            "type": "string",
            "description": f"{field_name} text",
        }
    elif field_name in ["previous", "consensus", "actual"]:
        return {
            "type": "string",
            "pattern": "^[0-9]+(\\.[0-9]+)?$",
            "description": f"{field_name} value as decimal string",
        }
    elif field_name == "category":
        return {
            "type": "string",
            "description": "Category identifier",
        }
    else:
        # Default to string for unknown fields
        return {
            "type": "string",
            "description": f"{field_name} field",
        }
