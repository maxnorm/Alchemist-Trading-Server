# C4 Level 1 - System Context Diagram

## Purpose
This diagram answers: **Who uses the Alchemist platform and what external systems does it interact with?**

## Scope
- **Includes**: All actors (users/systems) and external system boundaries
- **Excludes**: Internal container/component details

## Source of Truth References
| Element | Evidence Path |
|---------|---------------|
| MT5 EA Integration | `src/utils/MT5-EA/EAs/*.mq5`, `src/trading_server/src/server.py:337-463` |
| Clerk Authentication | `src/api/src/middleware/auth.py`, `src/dashboard/src/config/clerk.ts` |
| Myfxbook Scraping | `src/trading_server/src/web_scraper/web_scraper_myfxbook.py` |
| External Data APIs | `src/trading_server/src/connectors/fred_connector.py`, `src/trading_server/src/connectors/ecb_connector.py`, `src/trading_server/src/connectors/news_api_connector.py` |

## System Context Diagram

```mermaid
C4Context
    title System Context Diagram - Alchemist AI Trading Platform

    Person(trader, "Trader/Researcher", "Creates experiments, monitors training, manages models and live trading")
    Person(admin, "Platform Admin", "Manages platform configuration, monitors system health")

    System(alchemist, "Alchemist Platform", "AI Forex Experimentation & Trading Platform for DRL model development and deployment")

    System_Ext(mt5, "MetaTrader 5", "Trading terminal platform - connects via Expert Advisors for tick streaming and trade execution")
    System_Ext(clerk, "Clerk", "External authentication & identity provider for user management")
    System_Ext(myfxbook, "Myfxbook", "Economic calendar data source - web scraping")
    System_Ext(fred, "FRED API", "Federal Reserve Economic Data - macroeconomic indicators")
    System_Ext(ecb, "ECB Data Portal", "European Central Bank - exchange rates and indicators")
    System_Ext(newsapi, "NewsAPI", "News articles and sentiment data")
    System_Ext(worldbank, "World Bank API", "Global economic indicators")
    System_Ext(rss, "RSS Feeds", "Financial news feeds")

    Rel(trader, alchemist, "Uses", "HTTPS/WSS")
    Rel(admin, alchemist, "Manages", "HTTPS/WSS")
    
    Rel(alchemist, mt5, "Receives tick data, sends trade orders", "TCP Socket (8080)")
    Rel(alchemist, clerk, "Authenticates users", "HTTPS REST API")
    Rel(alchemist, myfxbook, "Scrapes economic calendar", "HTTPS")
    Rel(alchemist, fred, "Fetches economic data", "HTTPS REST API")
    Rel(alchemist, ecb, "Fetches exchange rates", "HTTPS REST API")
    Rel(alchemist, newsapi, "Fetches news articles", "HTTPS REST API")
    Rel(alchemist, worldbank, "Fetches indicators", "HTTPS REST API")
    Rel(alchemist, rss, "Fetches news feeds", "HTTPS RSS")

    UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

## Alternative Mermaid Flowchart (GitHub Compatible)

```mermaid
flowchart TB
    subgraph Users["👥 Users"]
        Trader["🧑‍💼 Trader/Researcher<br/>Creates experiments, monitors training"]
        Admin["👨‍💻 Platform Admin<br/>Manages configuration"]
    end

    subgraph Alchemist["🧪 Alchemist Platform"]
        Platform["AI Forex Experimentation<br/>& Trading Platform"]
    end

    subgraph ExternalSystems["🌐 External Systems"]
        MT5["🏦 MetaTrader 5<br/>Trading Terminal"]
        Clerk["🔐 Clerk<br/>Auth Provider"]
        
        subgraph DataSources["📊 Data Sources"]
            Myfxbook["📅 Myfxbook<br/>Economic Calendar"]
            FRED["📈 FRED API<br/>Fed Reserve Data"]
            ECB["🇪🇺 ECB Portal<br/>Exchange Rates"]
            NewsAPI["📰 NewsAPI<br/>News & Sentiment"]
            WorldBank["🌍 World Bank<br/>Economic Indicators"]
            RSS["📡 RSS Feeds<br/>Financial News"]
        end
    end

    Trader -->|"HTTPS/WSS"| Platform
    Admin -->|"HTTPS/WSS"| Platform
    
    Platform <-->|"TCP:8080<br/>Tick Stream + Orders"| MT5
    Platform -->|"HTTPS<br/>Token Verification"| Clerk
    
    Platform -->|"HTTPS Scraping"| Myfxbook
    Platform -->|"REST API"| FRED
    Platform -->|"REST API"| ECB
    Platform -->|"REST API"| NewsAPI
    Platform -->|"REST API"| WorldBank
    Platform -->|"RSS"| RSS

    style Platform fill:#1168bd,stroke:#0b4884,color:#fff
    style MT5 fill:#999999,stroke:#666666,color:#fff
    style Clerk fill:#6c5ce7,stroke:#5649c0,color:#fff
```

## Key Interactions

| From | To | Protocol | Purpose |
|------|-----|----------|---------|
| Trader/Admin | Alchemist | HTTPS/WSS | Web dashboard access, API calls, real-time updates |
| Alchemist | MetaTrader 5 | TCP Socket (8080) | Tick data streaming, trade order execution via Expert Advisors |
| Alchemist | Clerk | HTTPS REST | JWT token verification, user identity management |
| Alchemist | Myfxbook | HTTPS | Web scraping for economic calendar events |
| Alchemist | FRED/ECB/WorldBank | HTTPS REST | Macroeconomic data for feature engineering |
| Alchemist | NewsAPI/RSS | HTTPS | News and sentiment data for alternative data features |

## Assumptions
- **None** - All external integrations are verified in codebase

## Open Questions
- **None** - All actors and integrations are documented in code
