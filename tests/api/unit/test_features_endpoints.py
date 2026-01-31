"""
Tests for feature catalog API endpoints
"""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime


class TestListFeatures:
    """GET /api/features - List all features"""
    
    def test_list_features(self, api_client):
        """Test listing all features"""
        from schemas.features import FeatureResponse
        from services import feature_service
        
        with patch.object(feature_service, 'get_all_features') as mock_get:
            mock_get.return_value = [
                FeatureResponse(
                    id=1,
                    name="price_bid_EURUSD",
                    data_type="float",
                    source="price",
                    description="Bid price",
                    category="price",
                    created_at=datetime.utcnow()
                ),
                FeatureResponse(
                    id=2,
                    name="rsi_14_EURUSD",
                    data_type="float",
                    source="indicator",
                    description="RSI indicator",
                    category="technical",
                    created_at=datetime.utcnow()
                )
            ]
            
            response = api_client.get("/api/v1/features")
            
            assert response.status_code == 200
            data = response.json()
            assert "features" in data
            assert len(data["features"]) == 2
            assert data["total"] == 2
    
    def test_list_features_filter_by_source(self, api_client):
        """Test filtering features by source"""
        from schemas.features import FeatureResponse
        
        from services import feature_service
        with patch.object(feature_service, 'get_all_features') as mock_get:
            mock_get.return_value = [
                FeatureResponse(
                    id=1,
                    name="price_bid_EURUSD",
                    data_type="float",
                    source="price",
                    description="Bid price",
                    category="price",
                    created_at=datetime.utcnow()
                )
            ]
            
            response = api_client.get("/api/v1/features?source=price")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["features"]) == 1
            assert data["features"][0]["source"] == "price"
    
    def test_list_features_filter_by_category(self, api_client):
        """Test filtering features by category"""
        from schemas.features import FeatureResponse
        
        from services import feature_service
        with patch.object(feature_service, 'get_all_features') as mock_get:
            mock_get.return_value = [
                FeatureResponse(
                    id=1,
                    name="rsi_14_EURUSD",
                    data_type="float",
                    source="indicator",
                    description="RSI indicator",
                    category="technical",
                    created_at=datetime.utcnow()
                )
            ]
            
            response = api_client.get("/api/v1/features?category=technical")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["features"]) == 1
            assert data["features"][0]["category"] == "technical"


class TestGetFeatureDetails:
    """GET /api/features/{name} - Get feature details"""
    
    def test_get_feature_details(self, api_client):
        """Test getting feature details"""
        from schemas.features import FeatureResponse
        
        with patch('routers.features.get_feature_by_name') as mock_get:
            mock_get.return_value = FeatureResponse(
                id=1,
                name="price_bid_EURUSD",
                data_type="float",
                source="price",
                description="Bid price for EURUSD",
                category="price",
                is_available=True,
                created_at=datetime.utcnow()
            )
            
            response = api_client.get("/api/v1/features/price_bid_EURUSD")
            
            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "price_bid_EURUSD"
            assert data["source"] == "price"
    
    def test_get_feature_not_found(self, api_client):
        """Test 404 for non-existent feature"""
        with patch('routers.features.get_feature_by_name') as mock_get:
            mock_get.return_value = None
            
            response = api_client.get("/api/v1/features/nonexistent_feature")
            
            assert response.status_code == 404
            data = response.json()
            # Custom exception handler returns {"error": ..., "status_code": ...}
            assert "error" in data or "detail" in data
            error_msg = data.get("error") or data.get("detail", "")
            assert "not found" in error_msg.lower()
