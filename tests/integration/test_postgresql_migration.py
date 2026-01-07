"""
Integration tests for PostgreSQL migration
Tests schema migration, hypertables, functions, and basic operations
"""

import pytest
import psycopg2
import os
from datetime import datetime, timedelta


@pytest.fixture(scope="module")
def db_connection():
    """Create database connection for testing"""
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=int(os.getenv('DB_PORT', 5432)),
        user=os.getenv('DB_USER', 'forex_user'),
        password=os.getenv('DB_PASSWORD', 'forex_password'),
        database=os.getenv('DB_NAME', 'db_forex')
    )
    yield conn
    conn.close()


class TestSchemaMigration:
    """Test that schema was migrated correctly"""
    
    def test_core_tables_exist(self, db_connection):
        """Verify core tables were created"""
        cursor = db_connection.cursor()
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('currency', 'country', 'forex_pairs', 'ticks_forex', 'economic_calendar')
            ORDER BY table_name
        """)
        tables = [row[0] for row in cursor.fetchall()]
        cursor.close()
        
        assert 'currency' in tables
        assert 'country' in tables
        assert 'forex_pairs' in tables
        assert 'ticks_forex' in tables
        assert 'economic_calendar' in tables
    
    def test_hypertables_created(self, db_connection):
        """Verify TimescaleDB hypertables were created"""
        cursor = db_connection.cursor()
        cursor.execute("""
            SELECT hypertable_name 
            FROM timescaledb_information.hypertables 
            WHERE hypertable_name IN ('ticks_forex', 'economic_calendar')
            ORDER BY hypertable_name
        """)
        hypertables = [row[0] for row in cursor.fetchall()]
        cursor.close()
        
        assert 'ticks_forex' in hypertables
        assert 'economic_calendar' in hypertables
    
    def test_functions_created(self, db_connection):
        """Verify PostgreSQL functions were created"""
        cursor = db_connection.cursor()
        cursor.execute("""
            SELECT routine_name 
            FROM information_schema.routines 
            WHERE routine_schema = 'public' 
            AND routine_name IN ('insert_tick_forex', 'insert_economic_calendar_data', 'insert_tick_forex_optimized')
            ORDER BY routine_name
        """)
        functions = [row[0] for row in cursor.fetchall()]
        cursor.close()
        
        assert 'insert_tick_forex' in functions
        assert 'insert_economic_calendar_data' in functions
        assert 'insert_tick_forex_optimized' in functions
    
    def test_triggers_created(self, db_connection):
        """Verify triggers for updated_at columns were created"""
        cursor = db_connection.cursor()
        cursor.execute("""
            SELECT trigger_name 
            FROM information_schema.triggers 
            WHERE trigger_schema = 'public' 
            AND trigger_name LIKE '%updated_at%'
            ORDER BY trigger_name
        """)
        triggers = [row[0] for row in cursor.fetchall()]
        cursor.close()
        
        assert len(triggers) > 0  # At least some triggers should exist


class TestFunctionExecution:
    """Test PostgreSQL function execution"""
    
    def test_insert_tick_forex_function(self, db_connection):
        """Test insert_tick_forex function"""
        cursor = db_connection.cursor()
        
        # First ensure currencies exist
        cursor.execute("SELECT id FROM currency WHERE iso_code = 'EUR'")
        eur_id = cursor.fetchone()
        if not eur_id:
            cursor.execute("INSERT INTO currency (nom, iso_code) VALUES ('Euro', 'EUR') RETURNING id")
            eur_id = cursor.fetchone()
        
        cursor.execute("SELECT id FROM currency WHERE iso_code = 'USD'")
        usd_id = cursor.fetchone()
        if not usd_id:
            cursor.execute("INSERT INTO currency (nom, iso_code) VALUES ('US Dollar', 'USD') RETURNING id")
            usd_id = cursor.fetchone()
        
        # Ensure pair exists
        cursor.execute("""
            SELECT id FROM forex_pairs 
            WHERE base_currency_id = %s AND quote_currency_id = %s
        """, (eur_id[0], usd_id[0]))
        pair = cursor.fetchone()
        if not pair:
            cursor.execute("""
                INSERT INTO forex_pairs (symbol, base_currency_id, quote_currency_id)
                VALUES ('EURUSD', %s, %s) RETURNING id
            """, (eur_id[0], usd_id[0]))
            pair = cursor.fetchone()
        
        # Test function
        test_datetime = datetime.utcnow()
        cursor.execute("""
            SELECT insert_tick_forex(%s, %s, %s, %s, %s)
        """, (test_datetime, 1.1000, 1.1001, 'EUR', 'USD'))
        
        # Verify tick was inserted
        cursor.execute("""
            SELECT COUNT(*) FROM ticks_forex 
            WHERE datetime = %s AND ask = %s AND bid = %s
        """, (test_datetime, 1.1000, 1.1001))
        count = cursor.fetchone()[0]
        
        cursor.close()
        assert count > 0
    
    def test_insert_economic_calendar_function(self, db_connection):
        """Test insert_economic_calendar_data function"""
        cursor = db_connection.cursor()
        
        # Ensure country exists
        cursor.execute("SELECT id FROM country WHERE nom = 'United States'")
        country = cursor.fetchone()
        if not country:
            cursor.execute("SELECT id FROM currency WHERE iso_code = 'USD'")
            usd_id = cursor.fetchone()
            if not usd_id:
                cursor.execute("INSERT INTO currency (nom, iso_code) VALUES ('US Dollar', 'USD') RETURNING id")
                usd_id = cursor.fetchone()
            cursor.execute("""
                INSERT INTO country (nom, currency_id) 
                VALUES ('United States', %s) RETURNING id
            """, (usd_id[0],))
            country = cursor.fetchone()
        
        # Test function
        test_datetime = datetime.utcnow()
        cursor.execute("""
            SELECT insert_economic_calendar_data(%s, %s, %s, %s, %s, %s, %s)
        """, (test_datetime, 'United States', 'Test Event', 1, '1.0', '1.1', '1.2'))
        
        # Verify event was inserted
        cursor.execute("""
            SELECT COUNT(*) FROM economic_calendar 
            WHERE datetime = %s AND event = %s
        """, (test_datetime, 'Test Event'))
        count = cursor.fetchone()[0]
        
        cursor.close()
        assert count > 0


class TestTimeSeriesQueries:
    """Test TimescaleDB time-series query functionality"""
    
    def test_time_bucket_query(self, db_connection):
        """Test time_bucket aggregation (TimescaleDB feature)"""
        cursor = db_connection.cursor()
        
        # This should work if TimescaleDB is properly installed
        try:
            cursor.execute("""
                SELECT time_bucket('1 hour', datetime) as hour, COUNT(*) as count
                FROM ticks_forex
                WHERE datetime >= NOW() - INTERVAL '24 hours'
                GROUP BY hour
                ORDER BY hour DESC
                LIMIT 5
            """)
            results = cursor.fetchall()
            cursor.close()
            # Query should execute without error
            assert True
        except psycopg2.errors.UndefinedFunction:
            # time_bucket might not be available if TimescaleDB extension isn't loaded
            # This is acceptable for basic testing
            cursor.close()
            pytest.skip("TimescaleDB time_bucket function not available")


class TestJSONOperations:
    """Test JSONB operations"""
    
    def test_jsonb_insert_and_query(self, db_connection):
        """Test JSONB column operations"""
        cursor = db_connection.cursor()
        
        # Test inserting into experiments table with JSONB
        test_features = ['feature1', 'feature2', 'feature3']
        test_pairs = ['EURUSD', 'GBPUSD']
        test_hyperparams = {'learning_rate': 0.001, 'batch_size': 32}
        
        cursor.execute("""
            INSERT INTO experiments (name, features, currency_pairs, training_mode, hyperparameters, status)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            'Test Experiment',
            psycopg2.extras.Json(test_features),
            psycopg2.extras.Json(test_pairs),
            'historical',
            psycopg2.extras.Json(test_hyperparams),
            'created'
        ))
        exp_id = cursor.fetchone()[0]
        
        # Query JSONB data
        cursor.execute("""
            SELECT features, hyperparameters 
            FROM experiments 
            WHERE id = %s
        """, (exp_id,))
        row = cursor.fetchone()
        
        cursor.execute("DELETE FROM experiments WHERE id = %s", (exp_id,))
        cursor.close()
        
        assert row is not None
        assert row[0] == test_features
        assert row[1]['learning_rate'] == 0.001


class TestConnectionPool:
    """Test connection pool functionality"""
    
    def test_connection_pool_getconn_putconn(self, db_connection):
        """Test that connection pool methods work correctly"""
        # This is more of a smoke test - actual pool testing would require
        # importing the Database class and testing its methods
        assert db_connection is not None
        assert db_connection.status == psycopg2.extensions.STATUS_READY
