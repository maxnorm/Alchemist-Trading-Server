# Fixing NumPy 2.0 Compatibility Issue

## Problem

When trying to load `feature_engineer.pkl`, you may encounter:
```
AttributeError: _ARRAY_API not found
ImportError: numpy.core.multiarray failed to import
```

This happens because:
- You have **NumPy 2.0.0** installed
- The pickle file was created with **scikit-learn** compiled for **NumPy 1.x**
- NumPy 2.0 is not backward compatible with modules compiled for NumPy 1.x

## Solution

### Option 1: Downgrade NumPy (Recommended)

Downgrade NumPy to a compatible version:

```bash
pip install "numpy<2"
```

Or specifically:
```bash
pip install numpy==1.26.4
```

Then verify:
```bash
python -c "import numpy; print(numpy.__version__)"
```

### Option 2: Upgrade scikit-learn and scipy

Upgrade to versions compatible with NumPy 2.0:

```bash
pip install --upgrade scikit-learn scipy
```

**Note**: This may require rebuilding some packages and might not work if they're not yet compatible.

### Option 3: Use a Virtual Environment

Create a clean environment with compatible versions:

```bash
# Create virtual environment
python -m venv venv_feature_engineer

# Activate (Windows)
venv_feature_engineer\Scripts\activate

# Activate (Linux/Mac)
source venv_feature_engineer/bin/activate

# Install compatible versions
pip install "numpy<2" scikit-learn scipy
```

## Verify the Fix

After fixing, test loading the pickle:

```python
import pickle
import sys
import os

# Add path
sys.path.insert(0, 'src/mt5-python_server/src')

with open('feature_engineer.pkl', 'rb') as f:
    feature_engineer = pickle.load(f)

print("SUCCESS: Loaded feature_engineer.pkl")
print(f"Normalization: {feature_engineer.normalization_method}")
print(f"Features: {len(feature_engineer.feature_names)}")
```

Or use the inspection script:
```bash
python inspect_feature_engineer_fixed.py feature_engineer.pkl
```

## Current Environment Check

Check your current versions:
```bash
python -c "import numpy; print('NumPy:', numpy.__version__)"
python -c "import sklearn; print('scikit-learn:', sklearn.__version__)"
python -c "import scipy; print('SciPy:', scipy.__version__)"
```

## Recommended Versions

For compatibility with the existing pickle file:
- **NumPy**: 1.21.6 - 1.26.4
- **scikit-learn**: 1.0.0 - 1.3.2
- **SciPy**: 1.7.0 - 1.11.4

## Alternative: Inspect Without Loading

If you just need to inspect the file without loading it, use:
```bash
python inspect_pickle_direct.py feature_engineer.pkl
```

This script works without importing sklearn or numpy.
