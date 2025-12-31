# Understanding feature_engineer.pkl Files

## Overview

The `feature_engineer.pkl` file is a serialized (pickled) `FeatureEngineer` object that contains pre-fitted scalers for normalizing trading features. This file is used to ensure consistent feature scaling between training and inference.

## File Structure

The pickle file contains a `FeatureEngineer` instance with the following components:

### 1. Basic Attributes

- **`normalization_method`**: The normalization technique used (typically `'robust'`, `'standard'`, or `'minmax'`)
- **`is_fitted`**: Boolean indicating whether the scalers have been fitted on training data
- **`feature_names`**: List of feature names in the order they should be provided
- **`scalers`**: Dictionary mapping feature names to their fitted scaler objects

### 2. Feature Names

Based on the pickle file structure, the features typically include:

1. `sma_20` - Simple Moving Average (20 period)
2. `sma_50` - Simple Moving Average (50 period)
3. `ema_12` - Exponential Moving Average (12 period)
4. `ema_26` - Exponential Moving Average (26 period)
5. `rsi` - Relative Strength Index
6. `macd` - MACD line
7. `macd_signal` - MACD signal line
8. `macd_histogram` - MACD histogram
9. `bb_upper` - Bollinger Bands upper band
10. `bb_middle` - Bollinger Bands middle band
11. `bb_lower` - Bollinger Bands lower band
12. `bb_width` - Bollinger Bands width
13. `price_change` - Price change
14. `price_change_pct` - Price change percentage
15. `price` - Current price

### 3. Scaler Objects

Each feature has a corresponding scaler (typically `RobustScaler` from scikit-learn) that contains:

- **`center_`**: The median (for RobustScaler) or mean (for StandardScaler) used for centering
- **`scale_`**: The interquartile range (for RobustScaler) or standard deviation (for StandardScaler) used for scaling
- **`n_features_in_`**: Number of input features (usually 1 for each feature)
- **`quantile_range`**: For RobustScaler, the quantile range used (default: (25.0, 75.0))
- **`with_centering`**: Whether centering is applied
- **`with_scaling`**: Whether scaling is applied

## How It Works

### During Training

1. Features are extracted from market data
2. The `FeatureEngineer` is fitted on the training data
3. Each feature's scaler learns the center and scale values
4. The fitted `FeatureEngineer` is saved as a pickle file

### During Inference

1. The `FeatureEngineer` is loaded from the pickle file
2. New features are transformed using the pre-fitted scalers
3. Features are normalized using: `(value - center) / scale`
4. The normalized features are used for model predictions

## Usage Example

```python
import pickle
import numpy as np
from src.mt5_python_server.src.utils.feature_engineering import FeatureEngineer

# Load the fitted feature engineer
with open('feature_engineer.pkl', 'rb') as f:
    feature_engineer = pickle.load(f)

# Prepare features (must include all features from feature_names)
features = {
    'sma_20': np.array([1.2345]),
    'sma_50': np.array([1.2340]),
    'ema_12': np.array([1.2343]),
    'ema_26': np.array([1.2341]),
    'rsi': np.array([55.5]),
    'macd': np.array([0.0001]),
    'macd_signal': np.array([0.0002]),
    'macd_histogram': np.array([-0.0001]),
    'bb_upper': np.array([1.2400]),
    'bb_middle': np.array([1.2345]),
    'bb_lower': np.array([1.2290]),
    'bb_width': np.array([0.0110]),
    'price_change': np.array([0.0005]),
    'price_change_pct': np.array([0.0405]),
    'price': np.array([1.2345])
}

# Transform features (normalize them)
normalized_features = feature_engineer.transform(features)
# Returns: numpy array of shape (1, n_features) with normalized values
```

## File Location

The file can be located at:
- Root directory: `feature_engineer.pkl`
- Model-specific: `models/account_452449/scalers/feature_engineer.pkl`

## Normalization Methods

### RobustScaler (Default)
- Uses median and IQR (Interquartile Range)
- Robust to outliers
- Formula: `(x - median) / IQR`
- Best for financial data with outliers

### StandardScaler
- Uses mean and standard deviation
- Formula: `(x - mean) / std`
- Assumes normal distribution

### MinMaxScaler
- Scales to [0, 1] range
- Formula: `(x - min) / (max - min)`
- Sensitive to outliers

## Important Notes

1. **Feature Order**: Features must be provided in the same order as `feature_names`
2. **All Features Required**: All features listed in `feature_names` must be present when calling `transform()`
3. **NaN Handling**: NaN values are replaced with 0 after normalization
4. **Consistency**: The same pickle file used during training must be used during inference
5. **Version Compatibility**: Ensure compatible versions of scikit-learn and NumPy when loading

## Inspecting the File

To inspect the contents of a pickle file, you can use:

```python
import pickle

with open('feature_engineer.pkl', 'rb') as f:
    fe = pickle.load(f)
    
print(f"Normalization method: {fe.normalization_method}")
print(f"Features: {fe.feature_names}")
print(f"Number of scalers: {len(fe.scalers)}")
```

## Troubleshooting

### ModuleNotFoundError: No module named 'utils'
- Ensure the Python path includes `src/mt5-python_server/src`
- Or use the full import path: `from src.mt5_python_server.src.utils.feature_engineering import FeatureEngineer`

### NumPy Version Issues
- The pickle file may have been created with a different NumPy version
- Try matching the NumPy version used during training
- Or recreate the pickle file with the current environment

### Missing Features
- Ensure all features from `feature_names` are provided
- Check that feature names match exactly (case-sensitive)
