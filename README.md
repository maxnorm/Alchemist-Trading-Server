# funds

## Description
This repository contains a set of tools for trading purposes.
It is based on the MetaTrader 5 platform (https://www.metatrader5.com/en) and Python 3.11.

The main goal is to collect tick data from the MetaTrader 5 platform and store it into a database. 
The data can be used for backtesting purposes or for the development trading models.
The repository also contains a Python server for trading purposes.

## Features
- Collect tick data from the MetaTrader 5 platform and store it into a database.
- Collect economic data from MyFxBook (https://www.myfxbook.com/) and store it into a database.
- Trading server for sending orders to the MetaTrader 5 platform.

## Installation
### MetaTrader 5
- Download and install the MetaTrader 5 platform (https://www.metatrader5.com/en/download).
- Open the MetaTrader 5 platform and go to Tools -> Options -> Expert Advisors and check the following options:
  - Allow WebRequest for listed URL
  - Add URL: http://localhost:8080 to allow the communication with the Python server.