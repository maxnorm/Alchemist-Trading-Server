# The Alchemist
The Alchemist is a comprehensive trading system that integrates with MetaTrader 5 (MT5) platform. It serves as a data collection and trading execution system with multiple capabilities.

## Core Functionalities
1. **Data Collection**
   - Real-time tick data collection from MT5
   - Economic data harvesting from MyFxBook
   - Database storage for collected data

2. **Trading Operations**
   - Direct terminal connection to MT5 Expert Advisors (EA)
   - Account information retrieval
   - Order management (sending and closing)

## Requirements
- Docker and Docker Compose
- Python 3.11
- MetaTrader 5 platform with a valid paper or live account

## Quick Start
```bash
docker compose up -d --build
```

## MT5 Platform Configuration
1. Install MetaTrader 5 from the [official website](https://www.metatrader5.com/en/download)
2. Configure Expert Advisors:
   - Navigate to: Tools -> Options -> Expert Advisors
   - Enable "Allow WebRequest for listed URL"
   - Add your endpoint: `http://<your ip>:<your port>`


## License
Proprietary software of Alchemist Capital

Unauthorized use or distribution is prohibited

© 2025, Alchemist Capital - All rights reserved