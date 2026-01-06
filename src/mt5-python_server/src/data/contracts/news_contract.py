"""
News data contract validator
Validates news data against schema contract v1.0.0
"""

from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from .base import IContractValidator


class NewsContractValidator(IContractValidator):
    """
    Validator for news data contract v1.0.0
    Validates structure, types, formats, and constraints for news data
    """
    
    CONTRACT_VERSION = "1.0.0"
    DATA_TYPE = "news"
    
    # Required fields
    REQUIRED_FIELDS = ["symbol", "datetime", "title", "source"]
    
    # Optional fields
    OPTIONAL_FIELDS = ["content", "impact", "category", "receive_time"]
    
    # Valid impact levels
    VALID_IMPACTS = ["low", "medium", "high"]
    
    # Field length constraints
    MAX_TITLE_LENGTH = 500
    MAX_CONTENT_LENGTH = 10000
    MAX_SOURCE_LENGTH = 100
    
    def get_contract_version(self) -> str:
        """Return contract version"""
        return self.CONTRACT_VERSION
    
    def get_data_type(self) -> str:
        """Return data type identifier"""
        return self.DATA_TYPE
    
    def validate(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate news data against contract
        
        :param data: News data dictionary
        :return: Tuple of (is_valid, error_message)
        """
        # Check required fields
        for field in self.REQUIRED_FIELDS:
            if field not in data or data[field] is None:
                return False, f"Missing required field: {field}"
        
        # Validate symbol (can be "*" for general news or valid currency pair)
        if not isinstance(data["symbol"], str):
            return False, "Field 'symbol' must be a string"
        
        symbol = data["symbol"].strip()
        if symbol != "*":
            symbol_error = self.validate_symbol_format(symbol)
            if symbol_error:
                return False, symbol_error
        
        # Validate datetime
        datetime_error = self.validate_datetime_utc(data["datetime"], "datetime")
        if datetime_error:
            return False, datetime_error
        
        # Validate title
        if not isinstance(data["title"], str):
            return False, "Field 'title' must be a string"
        
        title = data["title"].strip()
        if len(title) == 0:
            return False, "Field 'title' cannot be empty"
        
        if len(title) > self.MAX_TITLE_LENGTH:
            return False, f"Field 'title' exceeds maximum length of {self.MAX_TITLE_LENGTH} characters"
        
        # Validate source
        if not isinstance(data["source"], str):
            return False, "Field 'source' must be a string"
        
        source = data["source"].strip()
        if len(source) == 0:
            return False, "Field 'source' cannot be empty"
        
        if len(source) > self.MAX_SOURCE_LENGTH:
            return False, f"Field 'source' exceeds maximum length of {self.MAX_SOURCE_LENGTH} characters"
        
        # Validate optional content
        if "content" in data and data["content"] is not None:
            if not isinstance(data["content"], str):
                return False, "Field 'content' must be a string"
            
            if len(data["content"]) > self.MAX_CONTENT_LENGTH:
                return False, f"Field 'content' exceeds maximum length of {self.MAX_CONTENT_LENGTH} characters"
        
        # Validate optional impact
        if "impact" in data and data["impact"] is not None:
            if not isinstance(data["impact"], str):
                return False, "Field 'impact' must be a string"
            
            if data["impact"] not in self.VALID_IMPACTS:
                return False, f"Field 'impact' must be one of {self.VALID_IMPACTS}, got '{data['impact']}'"
        
        # Validate optional category (no specific constraints, just must be string if present)
        if "category" in data and data["category"] is not None:
            if not isinstance(data["category"], str):
                return False, "Field 'category' must be a string"
        
        # Validate optional receive_time
        if "receive_time" in data and data["receive_time"] is not None:
            receive_time_error = self.validate_datetime_utc(data["receive_time"], "receive_time")
            if receive_time_error:
                return False, receive_time_error
        
        # All validations passed
        return True, None
