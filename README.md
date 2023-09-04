# funds

Python server for trading engine purpose.

## Features
- Use a docker container for running a MariaDB database
- Collect tick data from the 28 majors forex pairs into database with MT5 EAs sending each tick via socket connection
- Update assets price live to subscribe strategy for incoming price update 
- Collect economic calendar data from MyFxBook website (https://www.myfxbook.com/forex-economic-calendar) and store it into the database


