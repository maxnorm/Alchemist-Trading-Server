from abc import ABC, abstractmethod
from typing import Dict, Any

class DataProvider(ABC):
    """Base class for all data providers"""
    
    @abstractmethod
    def get_current_data(self):
        """Return current data in standardized json format"""
        pass
        
    @abstractmethod
    def subscribe(self, callback):
        """Subscribe to data updates"""
        pass