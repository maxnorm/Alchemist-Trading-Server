"""
Integration tests for model assignment flow

Tests the complete flow from model assignment to TradingController creation.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime

from tests.shared.helpers.path_utils import setup_trading_server_path
setup_trading_server_path()

from services.model_assignment_service import ModelAssignmentService
from trading_controller import TradingController
from models.account import Account


class TestModelAssignmentFlow:
    """Test model assignment to live accounts"""

    @pytest.fixture
    def mock_server(self):
        """Create mock server instance"""
        server = Mock()
        server._Server__db = Mock()
        server._Server__environment_factory = Mock()
        server._Server__environment_factory.get_environment = Mock(return_value=None)
        server._Server__environment_factory.create_environment = Mock(return_value=Mock())
        server._Server__connector_registry = Mock()
        server._Server__connector_registry.get_connector = Mock(return_value=None)
        server._Server__connector_registry.get_all_connectors = Mock(return_value={})
        server.get_account = Mock()
        return server

    @pytest.fixture
    def mock_live_account(self):
        """Create mock live account"""
        account = Mock(spec=Account)
        account.login = 67890
        account.balance = 10000.0
        account.account_type = "live"
        account.broker_adapter = Mock()
        return account

    @pytest.fixture
    def mock_demo_account(self):
        """Create mock demo account"""
        account = Mock(spec=Account)
        account.login = 12345
        account.balance = 10000.0
        account.account_type = "demo"
        account.broker_adapter = Mock()
        return account

    @pytest.fixture
    def mock_model(self):
        """Create mock model"""
        from mlops.model_registry import Model, ModelStage
        
        model = Mock(spec=Model)
        model.id = 1
        model.version = "1.0.0"
        model.experiment_id = 100
        model.stage = Mock()
        model.stage.value = "production"
        model.features = ["feature1", "feature2"]
        model.mlflow_model_uri = "runs:/test-run/model"
        return model

    @pytest.fixture
    def service(self, mock_server):
        """Create ModelAssignmentService instance"""
        return ModelAssignmentService(server_instance=mock_server)

    def test_assign_model_to_live_account_success(
        self, service, mock_server, mock_live_account, mock_model
    ):
        """Test successful model assignment to live account"""
        # Setup mocks
        mock_server.get_account.return_value = mock_live_account
        
        with patch('services.model_assignment_service.ModelRegistry') as MockRegistry:
            mock_registry = MockRegistry.return_value
            mock_registry.get_model.return_value = mock_model
            mock_registry.get_model_path.return_value = "/tmp/model"
            
            with patch('services.model_assignment_service.AgentFactory') as MockAgentFactory:
                mock_agent = Mock()
                MockAgentFactory.create_agent.return_value = mock_agent
                
                with patch('services.model_assignment_service.TradingController') as MockController:
                    mock_controller = Mock(spec=TradingController)
                    MockController.return_value = mock_controller
                    
                    with patch('services.model_assignment_service.ExperimentRepository'):
                        with patch('services.model_assignment_service.Thread'):
                            # Execute assignment
                            result = service.handle_model_assignment(
                                account_id=1,
                                account_login=mock_live_account.login,
                                model_id=mock_model.id,
                                trading_mode="live",
                            )
                            
                            # Verify success
                            assert result is True
                            assert mock_live_account.login in service.controllers
                            
                            # Verify TradingController was created
                            MockController.assert_called_once()
                            
                            # Verify controller was started
                            assert mock_live_account.login in service.controller_threads

    def test_assign_model_rejects_demo_account_for_live_trading(
        self, service, mock_server, mock_demo_account, mock_model
    ):
        """Test that live trading mode rejects demo accounts"""
        # Setup mocks
        mock_server.get_account.return_value = mock_demo_account
        
        with patch('services.model_assignment_service.ModelRegistry') as MockRegistry:
            mock_registry = MockRegistry.return_value
            mock_registry.get_model.return_value = mock_model
            
            # Execute assignment - should fail validation
            result = service.handle_model_assignment(
                account_id=1,
                account_login=mock_demo_account.login,
                model_id=mock_model.id,
                trading_mode="live",
            )
            
            # Should return False due to validation failure
            assert result is False
            assert mock_demo_account.login not in service.controllers

    def test_assign_model_rejects_non_production_model(
        self, service, mock_server, mock_live_account
    ):
        """Test that non-production models are rejected for live trading"""
        # Setup mocks
        mock_server.get_account.return_value = mock_live_account
        
        # Create model in staging stage (not production)
        from mlops.model_registry import Model, ModelStage
        
        staging_model = Mock(spec=Model)
        staging_model.id = 2
        staging_model.stage = Mock()
        staging_model.stage.value = "staging"  # Not production
        
        with patch('services.model_assignment_service.ModelRegistry') as MockRegistry:
            mock_registry = MockRegistry.return_value
            mock_registry.get_model.return_value = staging_model
            
            # Execute assignment - should fail validation
            result = service.handle_model_assignment(
                account_id=1,
                account_login=mock_live_account.login,
                model_id=staging_model.id,
                trading_mode="live",
            )
            
            # Should return False due to validation failure
            assert result is False
            assert mock_live_account.login not in service.controllers

    def test_unassign_model_stops_trading(
        self, service, mock_server, mock_live_account
    ):
        """Test that unassignment stops TradingController"""
        # Setup: create a controller first
        mock_controller = Mock(spec=TradingController)
        service.controllers[mock_live_account.login] = mock_controller
        mock_thread = Mock()
        service.controller_threads[mock_live_account.login] = mock_thread
        
        # Execute unassignment
        result = service.handle_model_unassignment(mock_live_account.login)
        
        # Verify success
        assert result is True
        assert mock_live_account.login not in service.controllers
        assert mock_live_account.login not in service.controller_threads
        
        # Verify controller was stopped
        mock_controller.stop.assert_called_once()
        
        # Verify thread was joined
        mock_thread.join.assert_called_once()
