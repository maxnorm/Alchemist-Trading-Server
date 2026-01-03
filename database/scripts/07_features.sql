-- Migration script for features table
-- Phase 2: Data Source Plugin System
-- Creates table to store feature metadata from data providers

CREATE TABLE IF NOT EXISTS features (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) UNIQUE NOT NULL,
    data_type VARCHAR(20) NOT NULL,
    source VARCHAR(50) NOT NULL,
    description TEXT,
    category VARCHAR(50),
    available BOOLEAN DEFAULT TRUE,
    min_value DOUBLE,
    max_value DOUBLE,
    mean_value DOUBLE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_source (source),
    INDEX idx_category (category),
    INDEX idx_available (available),
    INDEX idx_name (name)
);

-- Add comment to table
ALTER TABLE features COMMENT = 'Feature catalog storing metadata for all available features from data providers';
