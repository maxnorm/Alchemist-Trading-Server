"""
Economic calendar data contract validator
Validates economic calendar data against schema contract v1.0.0
"""

from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from .base import IContractValidator


class EconomicContractValidator(IContractValidator):
    """
    Validator for economic calendar data contract v1.0.0
    Validates structure, types, formats, and constraints for economic calendar data
    """
    
    CONTRACT_VERSION = "1.0.0"
    DATA_TYPE = "economic"
    
    # Required fields
    REQUIRED_FIELDS = ["datetime", "country", "event", "impact"]
    
    # Optional fields
    OPTIONAL_FIELDS = ["previous", "consensus", "actual", "receive_time"]
    
    # Impact range
    MIN_IMPACT = 0
    MAX_IMPACT = 3
    
    def get_contract_version(self) -> str:
        """Return contract version"""
        return self.CONTRACT_VERSION
    
    def get_data_type(self) -> str:
        """Return data type identifier"""
        return self.DATA_TYPE
    
    def validate(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate economic calendar data against contract
        
        :param data: Economic calendar data dictionary
        :return: Tuple of (is_valid, error_message)
        """
        # Check required fields
        for field in self.REQUIRED_FIELDS:
            if field not in data or data[field] is None:
                return False, f"Missing required field: {field}"
        
        # Validate datetime
        datetime_error = self.validate_datetime_utc(data["datetime"], "datetime")
        if datetime_error:
            return False, datetime_error
        
        # Validate country (ISO country code, 2-3 characters)
        if not isinstance(data["country"], str):
            return False, "Field 'country' must be a string"
        
        country = data["country"].strip()
        if len(country) < 2 or len(country) > 3:
            return False, f"Field 'country' must be 2-3 characters (ISO code), got '{country}' ({len(country)} chars)"
        
        # Validate event
        if not isinstance(data["event"], str):
            return False, "Field 'event' must be a string"
        
        event = data["event"].strip()
        if len(event) == 0:
            return False, "Field 'event' cannot be empty"
        
        if len(event) > 250:
            return False, f"Field 'event' exceeds maximum length of 250 characters"
        
        # Validate impact (integer 0-3)
        impact_error = self.validate_field_type(data["impact"], int, "impact")
        if impact_error:
            return False, impact_error
        
        try:
            impact = int(data["impact"])
            if impact < self.MIN_IMPACT or impact > self.MAX_IMPACT:
                return False, f"Field 'impact' must be between {self.MIN_IMPACT} and {self.MAX_IMPACT}, got {impact}"
        except (ValueError, TypeError):
            return False, "Field 'impact' must be an integer"
        
        # Validate optional previous (must be parseable as number if provided)
        if "previous" in data and data["previous"] is not None:
            if not isinstance(data["previous"], str):
                return False, "Field 'previous' must be a string"
            
            previous_str = data["previous"].strip()
            if len(previous_str) > 0:
                try:
                    float(previous_str)
                except ValueError:
                    return False, f"Field 'previous' must be a parseable number, got '{previous_str}'"
        
        # Validate optional consensus (must be parseable as number if provided)
        if "consensus" in data and data["consensus"] is not None:
            if not isinstance(data["consensus"], str):
                return False, "Field 'consensus' must be a string"
            
            consensus_str = data["consensus"].strip()
            if len(consensus_str) > 0:
                try:
                    float(consensus_str)
                except ValueError:
                    return False, f"Field 'consensus' must be a parseable number, got '{consensus_str}'"
        
        # Validate optional actual (must be parseable as number if provided)
        if "actual" in data and data["actual"] is not None:
            if not isinstance(data["actual"], str):
                return False, "Field 'actual' must be a string"
            
            actual_str = data["actual"].strip()
            if len(actual_str) > 0:
                try:
                    float(actual_str)
                except ValueError:
                    return False, f"Field 'actual' must be a parseable number, got '{actual_str}'"
        
        # Validate optional receive_time
        if "receive_time" in data and data["receive_time"] is not None:
            receive_time_error = self.validate_datetime_utc(data["receive_time"], "receive_time")
            if receive_time_error:
                return False, receive_time_error
        
        # All validations passed
        return True, None
