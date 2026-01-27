"""
Compatibility Checker - Validates schema compatibility according to different modes
"""

import logging
from typing import Dict, Any, List, Set, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class CompatibilityMode(str, Enum):
    """Compatibility mode enumeration"""

    BACKWARD = "BACKWARD"  # New schema can read old data
    FORWARD = "FORWARD"  # Old schema can read new data
    FULL = "FULL"  # Both directions compatible
    NONE = "NONE"  # No compatibility checks


class CompatibilityError(Exception):
    """Exception raised when compatibility check fails"""

    pass


class CompatibilityChecker:
    """
    Checks compatibility between JSON schemas according to different modes.

    Supports JSON Schema Draft 7 format.
    """

    def validate_compatibility(
        self,
        old_schema: Dict[str, Any],
        new_schema: Dict[str, Any],
        mode: CompatibilityMode,
    ) -> bool:
        """
        Validate compatibility between two schemas

        :param old_schema: Old schema definition
        :param new_schema: New schema definition
        :param mode: Compatibility mode
        :return: True if compatible
        :raises CompatibilityError: If incompatible
        """
        if mode == CompatibilityMode.NONE:
            return True

        if mode == CompatibilityMode.BACKWARD:
            return self._check_backward_compatibility(old_schema, new_schema)
        elif mode == CompatibilityMode.FORWARD:
            return self._check_forward_compatibility(old_schema, new_schema)
        elif mode == CompatibilityMode.FULL:
            backward_ok = self._check_backward_compatibility(old_schema, new_schema)
            forward_ok = self._check_forward_compatibility(old_schema, new_schema)
            if not backward_ok or not forward_ok:
                raise CompatibilityError(
                    f"FULL compatibility check failed. BACKWARD: {backward_ok}, FORWARD: {forward_ok}"
                )
            return True
        else:
            raise ValueError(f"Unknown compatibility mode: {mode}")

    def _check_backward_compatibility(
        self, old_schema: Dict[str, Any], new_schema: Dict[str, Any]
    ) -> bool:
        """
        Check BACKWARD compatibility: New schema can read old data

        Rules:
        - ✅ Can add optional fields
        - ✅ Can add enum values
        - ❌ Cannot remove required fields
        - ❌ Cannot change field types
        - ❌ Cannot remove enum values
        """
        old_props = self._get_properties(old_schema)
        new_props = self._get_properties(new_schema)
        old_required = self._get_required_fields(old_schema)
        new_required = self._get_required_fields(new_schema)

        errors = []

        # Check: Cannot remove required fields
        removed_required = old_required - new_required
        if removed_required:
            errors.append(
                f"BACKWARD incompatible: Removed required fields: {removed_required}"
            )

        # Check each field in old schema
        for field_name, old_field_def in old_props.items():
            if field_name not in new_props:
                # Field removed - OK if optional, ERROR if required
                if field_name in old_required:
                    errors.append(
                        f"BACKWARD incompatible: Required field '{field_name}' removed"
                    )
                continue

            new_field_def = new_props[field_name]

            # Check: Cannot change field types
            old_type = self._get_field_type(old_field_def)
            new_type = self._get_field_type(new_field_def)
            if old_type != new_type:
                errors.append(
                    f"BACKWARD incompatible: Field '{field_name}' type changed from {old_type} to {new_type}"
                )

            # Check: Cannot remove enum values
            old_enum = self._get_enum_values(old_field_def)
            new_enum = self._get_enum_values(new_field_def)
            if old_enum and new_enum:
                removed_enum = set(old_enum) - set(new_enum)
                if removed_enum:
                    errors.append(
                        f"BACKWARD incompatible: Field '{field_name}' enum values removed: {removed_enum}"
                    )

        if errors:
            raise CompatibilityError("; ".join(errors))

        return True

    def _check_forward_compatibility(
        self, old_schema: Dict[str, Any], new_schema: Dict[str, Any]
    ) -> bool:
        """
        Check FORWARD compatibility: Old schema can read new data

        Rules:
        - ✅ Can remove optional fields
        - ✅ Can remove enum values
        - ❌ Cannot add required fields
        - ❌ Cannot change field types
        """
        old_props = self._get_properties(old_schema)
        new_props = self._get_properties(new_schema)
        old_required = self._get_required_fields(old_schema)
        new_required = self._get_required_fields(new_schema)

        errors = []

        # Check: Cannot add required fields
        added_required = new_required - old_required
        if added_required:
            errors.append(
                f"FORWARD incompatible: Added required fields: {added_required}"
            )

        # Check each field in new schema
        for field_name, new_field_def in new_props.items():
            if field_name not in old_props:
                # New field - OK if optional, ERROR if required
                if field_name in new_required:
                    errors.append(
                        f"FORWARD incompatible: Added required field '{field_name}'"
                    )
                continue

            old_field_def = old_props[field_name]

            # Check: Cannot change field types
            old_type = self._get_field_type(old_field_def)
            new_type = self._get_field_type(new_field_def)
            if old_type != new_type:
                errors.append(
                    f"FORWARD incompatible: Field '{field_name}' type changed from {old_type} to {new_type}"
                )

        if errors:
            raise CompatibilityError("; ".join(errors))

        return True

    def _get_properties(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Extract properties from JSON schema"""
        if "properties" in schema:
            return schema["properties"]
        return {}

    def _get_required_fields(self, schema: Dict[str, Any]) -> Set[str]:
        """Extract required fields from JSON schema"""
        if "required" in schema:
            return set(schema["required"])
        return set()

    def _get_field_type(self, field_def: Dict[str, Any]) -> Optional[str]:
        """Extract field type from field definition"""
        if "type" in field_def:
            return field_def["type"]
        # Handle array types
        if "items" in field_def:
            return "array"
        return None

    def _get_enum_values(self, field_def: Dict[str, Any]) -> Optional[List[Any]]:
        """Extract enum values from field definition"""
        if "enum" in field_def:
            return field_def["enum"]
        return None
