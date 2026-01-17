#!/bin/bash
# Execute a test order through the server
# Usage: bash scripts/run_test_order.sh

echo "Executing test order through server..."
docker compose exec server python -c "
import sys
sys.path.insert(0, '/app/src/trading_server/src')
import server
s = server._global_server_instance
if s:
    print('Sending test BUY order: EURUSD 0.01 lots')
    trade = s.send_test_order(452449, 'EURUSD', 0.01, 'BUY')
    if trade:
        print(f'Order executed! Ticket: {trade.ticket}')
    else:
        print('Order failed or rejected')
else:
    print('Server instance not found. Make sure server is running.')
"
