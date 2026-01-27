#!/bin/sh
set -e

# Substitute environment variables in prometheus.yml template
# Using envsubst if available, otherwise use Python as fallback
if command -v envsubst >/dev/null 2>&1; then
    envsubst < /etc/prometheus/prometheus.yml.template > /etc/prometheus/prometheus.yml
elif command -v python3 >/dev/null 2>&1; then
    # Python fallback for environment variable substitution with defaults
    python3 << 'PYTHON_SCRIPT'
import os
import re
import sys

def substitute_env_vars(content):
    """Substitute ${VAR:-default} patterns with environment variable values"""
    def replace_var(match):
        var_expr = match.group(1)
        # Handle ${VAR:-default} syntax
        if ':-' in var_expr:
            var_name, default = var_expr.split(':-', 1)
            value = os.getenv(var_name, default)
        else:
            value = os.getenv(var_expr, '')
        return str(value)
    
    # Match ${VAR} or ${VAR:-default}
    pattern = r'\$\{([^}]+)\}'
    return re.sub(pattern, replace_var, content)

with open('/etc/prometheus/prometheus.yml.template', 'r') as f:
    content = f.read()

substituted = substitute_env_vars(content)

with open('/etc/prometheus/prometheus.yml', 'w') as f:
    f.write(substituted)
PYTHON_SCRIPT
else
    # Final fallback: simple sed (won't handle defaults, but better than nothing)
    sed -e "s/\${API_PORT}/${API_PORT:-8000}/g" \
        -e "s/\${SERVER_PORT}/${SERVER_PORT:-8080}/g" \
        -e "s/\${PROMETHEUS_PORT}/${PROMETHEUS_PORT:-9090}/g" \
        /etc/prometheus/prometheus.yml.template > /etc/prometheus/prometheus.yml
fi

# Execute Prometheus with all arguments
exec prometheus "$@"
