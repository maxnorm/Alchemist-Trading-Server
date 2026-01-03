"""
Feature Engineering for Trading AI
Normalizes and prepares features for machine learning models
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler


class FeatureEngineer:
    """Feature engineering and normalization for trading data"""
    
    def __init__(self, normalization_method: str = 'robust'):
        """
        Initialize feature engineer
        :param normalization_method: 'standard', 'minmax', or 'robust'
        """
        self.normalization_method = normalization_method
        self.scalers = {}
        self.feature_names = []
        self.is_fitted = False
    
    def fit(self, features: Dict[str, np.ndarray]):
        """
        Fit scalers on training data
        :param features: Dictionary of feature arrays
        """
        self.feature_names = list(features.keys())
        
        for name, values in features.items():
            # Handle NaN values with forward-fill, then backward-fill
            # This preserves data continuity while handling missing values
            if np.any(np.isnan(values)):
                # Convert to pandas Series for efficient fill operations
                values_series = pd.Series(values)
                # Forward fill (use previous value), then backward fill (for leading NaNs)
                # Use ffill() and bfill() methods for better pandas compatibility
                values_filled = values_series.ffill().bfill()
                # If still NaN (all values were NaN), use zeros
                if values_filled.isna().any():
                    values_filled = values_filled.fillna(0.0)
                values_to_fit = values_filled.values
            else:
                values_to_fit = values
            
            if len(values_to_fit) > 0 and np.any(~np.isnan(values_to_fit)):
                if self.normalization_method == 'standard':
                    scaler = StandardScaler()
                elif self.normalization_method == 'minmax':
                    scaler = MinMaxScaler()
                else:  # robust
                    scaler = RobustScaler()
                
                # Reshape for scaler (needs 2D array)
                values_2d = values_to_fit.reshape(-1, 1)
                scaler.fit(values_2d)
                self.scalers[name] = scaler
        
        self.is_fitted = True
    
    def transform(self, features: Dict[str, np.ndarray]) -> np.ndarray:
        """
        Transform features using fitted scalers
        :param features: Dictionary of feature arrays
        :return: Normalized feature matrix (n_samples, n_features)
        """
        if not self.is_fitted:
            raise ValueError("FeatureEngineer must be fitted before transform")
        
        normalized_features = []
        
        for name in self.feature_names:
            if name in features:
                values = features[name].copy()
                
                # Handle NaN values (fill with 0 after normalization)
                nan_mask = np.isnan(values)
                
                if name in self.scalers:
                    # Reshape for scaler
                    values_2d = values.reshape(-1, 1)
                    normalized = self.scalers[name].transform(values_2d).flatten()
                else:
                    # No scaler available, use raw values
                    normalized = values
                
                # Fill NaN with 0
                normalized[nan_mask] = 0.0
                normalized_features.append(normalized)
            else:
                # Feature missing, fill with zeros
                if len(normalized_features) > 0:
                    normalized_features.append(np.zeros_like(normalized_features[0]))
                else:
                    raise ValueError(f"Feature {name} not found and no previous features to match shape")
        
        # Stack into matrix
        feature_matrix = np.column_stack(normalized_features)
        return feature_matrix
    
    def fit_transform(self, features: Dict[str, np.ndarray]) -> np.ndarray:
        """Fit and transform in one step"""
        self.fit(features)
        return self.transform(features)
    
    def create_state_vector(self, current_features: Dict[str, float], 
                           historical_features: Optional[List[Dict[str, np.ndarray]]] = None,
                           window_size: int = 50) -> np.ndarray:
        """
        Create state vector for RL agent
        :param current_features: Current feature values
        :param historical_features: Historical feature arrays (optional)
        :param window_size: Size of historical window
        :return: State vector shaped (window_size, n_features) or (n_features,) if no history
        """
        if historical_features:
            # Create sequence of features
            feature_sequences = []
            for i in range(min(window_size, len(historical_features))):
                feature_dict = {}
                for key, value_array in historical_features[i].items():
                    # Get the last value from each feature array
                    if len(value_array) > 0:
                        feature_dict[key] = value_array[-1]
                    else:
                        feature_dict[key] = 0.0
                feature_sequences.append(feature_dict)
            
            # Pad if necessary
            while len(feature_sequences) < window_size:
                feature_sequences.insert(0, {k: 0.0 for k in current_features.keys()})
            
            # Transform each timestep
            state_matrix = []
            for feat_dict in feature_sequences:
                normalized = self.transform({k: np.array([v]) for k, v in feat_dict.items()})
                state_matrix.append(normalized.flatten())
            
            return np.array(state_matrix)
        else:
            # Single timestep
            normalized = self.transform({k: np.array([v]) for k, v in current_features.items()})
            return normalized.flatten()
