CREATE OR REPLACE DATABASE db_forex;
USE db_forex;

CREATE OR REPLACE TABLE currency(
    id INT PRIMARY KEY AUTO_INCREMENT,
    nom VARCHAR(100) NOT NULL,
    iso_code CHAR(3) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
	updated_at TIMESTAMP NULL
);

CREATE OR REPLACE TABLE country(
    id INT PRIMARY KEY AUTO_INCREMENT,
    nom VARCHAR(100) NOT NULL,
    currency_id INT NOT NULL,
    CONSTRAINT currency_id_country
	    FOREIGN KEY (currency_id)
	    REFERENCES currency(id)
	    ON UPDATE CASCADE ON DELETE RESTRICT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
	updated_at TIMESTAMP NULL
);

CREATE OR REPLACE TABLE forex_pairs(
    id INT PRIMARY KEY AUTO_INCREMENT,
    symbol CHAR(6) NOT NULL,
    base_currency_id INT NOT NULL,
    CONSTRAINT base_currency_id_ticks
	    FOREIGN KEY (base_currency_id)
	    REFERENCES currency(id)
	    ON UPDATE CASCADE ON DELETE RESTRICT,
	quote_currency_id INT NOT NULL,
    CONSTRAINT quote_currency_id_ticks
	    FOREIGN KEY (quote_currency_id)
	    REFERENCES currency(id)
	    ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE OR REPLACE TABLE ticks_forex(
    id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    datetime DATETIME NOT NULL,
    ask DOUBLE NOT NULL,
    bid DOUBLE NOT NULL,
    volume DOUBLE,
    forex_pairs_id INT NOT NULL,
    CONSTRAINT forex_pairs_id_ticks
	    FOREIGN KEY (forex_pairs_id)
	    REFERENCES forex_pairs(id)
	    ON UPDATE CASCADE ON DELETE RESTRICT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
	updated_at TIMESTAMP NULL
);

CREATE OR REPLACE TABLE economic_calendar(
    id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    datetime DATETIME NOT NULL,
    event VARCHAR(250) NOT NULL,
    impact INT NOT NULL,
    previous VARCHAR(20),
    consensus VARCHAR(20),
    actual VARCHAR(20),
    country_id INT NOT NULL,
    CONSTRAINT country_id_economic_calendar
	    FOREIGN KEY (country_id)
	    REFERENCES country(id)
	    ON UPDATE CASCADE ON DELETE RESTRICT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
	updated_at TIMESTAMP NULL
)