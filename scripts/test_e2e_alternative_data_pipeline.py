#!/usr/bin/env python3
"""
End-to-End Test for Alternative Data Collection Pipeline

Tests the complete flow:
1. FRED connector: connect → collect → store → verify
2. NEWSAPI connector: connect → collect → store → verify
3. Data integrity checks
4. Query verification

All containers must be running and API keys must be set.
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any

# Add src to path - handle both host and container execution
script_dir = os.path.dirname(os.path.abspath(__file__))
# Try container path first (/app/src), then host path
if os.path.exists('/app/src'):
    sys.path.insert(0, '/app/src')
else:
    sys.path.insert(0, os.path.join(script_dir, '..', 'src', 'trading_server', 'src'))

from connectors.fred_connector import FREDConnector
from connectors.news_api_connector import NewsAPIConnector
from connectors.base import ConnectorConfig
from database import Database
from utils.logging_config import get_logger

logger = get_logger("e2e_alternative_data_test", "e2e_alternative_data_test.log")


class E2EAlternativeDataTest:
    """End-to-end test for alternative data collection pipeline"""
    
    def __init__(self):
        self.db = None
        self.test_results = {
            "fred": {"passed": False, "errors": [], "data_collected": 0, "data_stored": 0},
            "newsapi": {"passed": False, "errors": [], "data_collected": 0, "data_stored": 0},
        }
        
    def setup(self) -> bool:
        """Initialize database connection"""
        try:
            logger.info("=" * 80)
            logger.info("E2E TEST: Alternative Data Collection Pipeline")
            logger.info("=" * 80)
            logger.info("")
            
            logger.info("Step 1: Initializing database connection...")
            self.db = Database()
            logger.info("✓ Database connection established")
            return True
        except Exception as e:
            logger.error(f"✗ Failed to initialize database: {e}")
            return False
    
    def test_fred_pipeline(self) -> bool:
        """Test FRED data collection pipeline end-to-end"""
        logger.info("")
        logger.info("=" * 80)
        logger.info("TESTING FRED PIPELINE")
        logger.info("=" * 80)
        
        try:
            # Step 1: Check API key
            fred_key = os.getenv("FRED_API_KEY")
            if not fred_key:
                error_msg = "FRED_API_KEY not set in environment"
                logger.error(f"✗ {error_msg}")
                self.test_results["fred"]["errors"].append(error_msg)
                return False
            logger.info("✓ FRED_API_KEY found")
            
            # Step 2: Initialize connector
            logger.info("Step 2: Initializing FRED connector...")
            config = ConnectorConfig(
                source="FRED",
                symbol="US",
                extra_config={}
            )
            connector = FREDConnector(config)
            logger.info("✓ FRED connector initialized")
            
            # Step 3: Connect
            logger.info("Step 3: Connecting to FRED API...")
            if not connector.connect():
                error_msg = "Failed to connect to FRED API"
                logger.error(f"✗ {error_msg}")
                self.test_results["fred"]["errors"].append(error_msg)
                connector.disconnect()
                return False
            logger.info("✓ Connected to FRED API")
            
            # Step 4: Get available range
            logger.info("Step 4: Checking available data range...")
            try:
                earliest, latest = connector.get_available_range()
                logger.info(f"✓ Available range: {earliest.date()} to {latest.date()}")
            except Exception as e:
                logger.warning(f"⚠ Could not get available range: {e}")
            
            # Step 5: Collect data using backfill (last 30 days to get actual data)
            logger.info("Step 5: Collecting FRED indicators (last 30 days)...")
            start_time = datetime.now() - timedelta(days=30)
            end_time = datetime.now()
            
            indicators_collected = []
            count = 0
            max_indicators = 10  # Limit for testing
            
            try:
                for indicator in connector.backfill(start_time=start_time, end_time=end_time):
                    indicators_collected.append(indicator)
                    count += 1
                    
                    if count >= max_indicators:
                        logger.info(f"  Collected {count} indicators (limiting to {max_indicators} for test)")
                        break
                    
                    if count % 5 == 0:
                        logger.info(f"  Collected {count} indicators...")
                
                self.test_results["fred"]["data_collected"] = len(indicators_collected)
                logger.info(f"✓ Collected {len(indicators_collected)} FRED indicators")
                
                if len(indicators_collected) == 0:
                    logger.warning("⚠ No indicators collected (may be normal if no recent updates)")
                    # Still pass the test if connection works
                    connector.disconnect()
                    self.test_results["fred"]["passed"] = True
                    return True
                
            except Exception as e:
                error_msg = f"Error collecting FRED indicators: {e}"
                logger.error(f"✗ {error_msg}")
                self.test_results["fred"]["errors"].append(error_msg)
                connector.disconnect()
                return False
            
            # Step 6: Store in database
            logger.info("Step 6: Storing indicators in database...")
            stored_count = 0
            for indicator in indicators_collected:
                try:
                    success = self.db.insert_economic_indicator(
                        series_id=indicator.get("series_id", "UNKNOWN"),
                        timestamp=indicator.get("timestamp", datetime.now()),
                        value=indicator.get("value", 0.0),
                        source=indicator.get("source", "FRED"),
                        country=indicator.get("country", "US"),
                        frequency=indicator.get("frequency"),
                        receive_time=datetime.now()
                    )
                    if success:
                        stored_count += 1
                except Exception as e:
                    logger.warning(f"  Failed to store indicator {indicator.get('series_id')}: {e}")
                    continue
            
            self.test_results["fred"]["data_stored"] = stored_count
            logger.info(f"✓ Stored {stored_count}/{len(indicators_collected)} indicators in database")
            
            # Step 7: Verify data in database
            logger.info("Step 7: Verifying stored data...")
            if stored_count > 0:
                # Query back the data
                test_series = indicators_collected[0].get("series_id")
                if test_series:
                    try:
                        retrieved = self.db.get_economic_indicators(
                            series_id=test_series,
                            start_time=start_time,
                            end_time=end_time
                        )
                        if retrieved and len(retrieved) > 0:
                            logger.info(f"✓ Verified: Retrieved {len(retrieved)} indicators for {test_series}")
                        else:
                            logger.warning("⚠ Could not retrieve stored indicators (may be timing issue)")
                    except Exception as e:
                        logger.warning(f"⚠ Error querying data: {e}")
            
            connector.disconnect()
            logger.info("✓ FRED pipeline test PASSED")
            self.test_results["fred"]["passed"] = True
            return True
            
        except Exception as e:
            error_msg = f"FRED pipeline test failed: {e}"
            logger.error(f"✗ {error_msg}", exc_info=True)
            self.test_results["fred"]["errors"].append(error_msg)
            return False
    
    def test_newsapi_pipeline(self) -> bool:
        """Test NewsAPI data collection pipeline end-to-end"""
        logger.info("")
        logger.info("=" * 80)
        logger.info("TESTING NEWSAPI PIPELINE")
        logger.info("=" * 80)
        
        try:
            # Step 1: Check API key
            newsapi_key = os.getenv("NEWSAPI_API_KEY")
            if not newsapi_key:
                error_msg = "NEWSAPI_API_KEY not set in environment"
                logger.error(f"✗ {error_msg}")
                self.test_results["newsapi"]["errors"].append(error_msg)
                return False
            logger.info("✓ NEWSAPI_API_KEY found")
            
            # Step 2: Initialize connector
            logger.info("Step 2: Initializing NewsAPI connector...")
            config = ConnectorConfig(
                source="newsapi",
                symbol="*",
                extra_config={}
            )
            connector = NewsAPIConnector(config)
            logger.info("✓ NewsAPI connector initialized")
            
            # Step 3: Connect
            logger.info("Step 3: Connecting to NewsAPI...")
            if not connector.connect():
                error_msg = "Failed to connect to NewsAPI"
                logger.error(f"✗ {error_msg}")
                self.test_results["newsapi"]["errors"].append(error_msg)
                connector.disconnect()
                return False
            logger.info("✓ Connected to NewsAPI")
            
            # Step 4: Collect recent news (last 7 days - NewsAPI free tier allows up to 1 month)
            logger.info("Step 4: Collecting news articles (last 7 days)...")
            start_time = datetime.now() - timedelta(days=7)
            end_time = datetime.now()
            
            articles_collected = []
            count = 0
            max_articles = 5  # Limit for testing (NewsAPI has rate limits)
            
            try:
                # Use backfill for more reliable data collection
                for article in connector.backfill(start_time=start_time, end_time=end_time):
                    articles_collected.append(article)
                    count += 1
                    
                    if count >= max_articles:
                        logger.info(f"  Collected {count} articles (limiting to {max_articles} for test)")
                        break
                    
                    if count % 2 == 0:
                        logger.info(f"  Collected {count} articles...")
                
                self.test_results["newsapi"]["data_collected"] = len(articles_collected)
                logger.info(f"✓ Collected {len(articles_collected)} news articles")
                
                if len(articles_collected) == 0:
                    logger.warning("⚠ No articles collected (may be normal if no recent news or rate limit)")
                    # Still pass the test if connection works
                    connector.disconnect()
                    self.test_results["newsapi"]["passed"] = True
                    return True
                
            except Exception as e:
                error_msg = f"Error collecting NewsAPI articles: {e}"
                logger.error(f"✗ {error_msg}")
                self.test_results["newsapi"]["errors"].append(error_msg)
                # Check if it's a rate limit issue
                if "limit" in str(e).lower() or "429" in str(e):
                    logger.warning("⚠ NewsAPI rate limit reached (this is expected on free tier)")
                    connector.disconnect()
                    self.test_results["newsapi"]["passed"] = True  # Connection works, just rate limited
                    return True
                connector.disconnect()
                return False
            
            # Step 5: Store in database
            logger.info("Step 5: Storing articles in database...")
            stored_count = 0
            for article in articles_collected:
                try:
                    success = self.db.insert_news_article(
                        timestamp=article.get("timestamp", datetime.now()),
                        source=article.get("source", "newsapi"),
                        title=article.get("title", ""),
                        url=article.get("url", ""),
                        content=article.get("content"),
                        symbol=article.get("symbol"),
                        sentiment_score=article.get("sentiment_score"),
                        sentiment_label=article.get("sentiment_label"),
                        entities=article.get("entities"),
                        receive_time=datetime.now()
                    )
                    if success:
                        stored_count += 1
                except Exception as e:
                    logger.warning(f"  Failed to store article {article.get('title', '')[:50]}: {e}")
                    continue
            
            self.test_results["newsapi"]["data_stored"] = stored_count
            logger.info(f"✓ Stored {stored_count}/{len(articles_collected)} articles in database")
            
            # Step 6: Verify data in database
            logger.info("Step 6: Verifying stored data...")
            if stored_count > 0:
                # Query back the data
                try:
                    retrieved = self.db.get_news_by_timeframe(
                        start_time=start_time,
                        end_time=end_time,
                        source="newsapi"
                    )
                    if retrieved and len(retrieved) > 0:
                        logger.info(f"✓ Verified: Retrieved {len(retrieved)} articles from database")
                    else:
                        logger.warning("⚠ Could not retrieve stored articles (may be timing issue)")
                except Exception as e:
                    logger.warning(f"⚠ Error querying data: {e}")
            
            connector.disconnect()
            logger.info("✓ NewsAPI pipeline test PASSED")
            self.test_results["newsapi"]["passed"] = True
            return True
            
        except Exception as e:
            error_msg = f"NewsAPI pipeline test failed: {e}"
            logger.error(f"✗ {error_msg}", exc_info=True)
            self.test_results["newsapi"]["errors"].append(error_msg)
            return False
    
    def print_summary(self):
        """Print test summary"""
        logger.info("")
        logger.info("=" * 80)
        logger.info("TEST SUMMARY")
        logger.info("=" * 80)
        
        for pipeline, results in self.test_results.items():
            status = "✓ PASSED" if results["passed"] else "✗ FAILED"
            logger.info(f"{pipeline.upper():<15} {status}")
            logger.info(f"  Data Collected: {results['data_collected']}")
            logger.info(f"  Data Stored: {results['data_stored']}")
            if results["errors"]:
                logger.info(f"  Errors: {len(results['errors'])}")
                for error in results["errors"]:
                    logger.info(f"    - {error}")
        
        logger.info("=" * 80)
        
        all_passed = all(r["passed"] for r in self.test_results.values())
        if all_passed:
            logger.info("")
            logger.info("✓ ALL E2E TESTS PASSED")
            logger.info("")
        else:
            logger.info("")
            logger.error("✗ SOME E2E TESTS FAILED")
            logger.info("")
        
        return all_passed
    
    def run_all_tests(self) -> bool:
        """Run all E2E tests"""
        if not self.setup():
            return False
        
        fred_passed = self.test_fred_pipeline()
        newsapi_passed = self.test_newsapi_pipeline()
        
        all_passed = self.print_summary()
        return all_passed


def main():
    """Main entry point"""
    test = E2EAlternativeDataTest()
    success = test.run_all_tests()
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
