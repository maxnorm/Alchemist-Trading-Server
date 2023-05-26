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

CREATE OR REPLACE TABLE ticks_forex(
    id INT PRIMARY KEY AUTO_INCREMENT,
    datetime DATETIME NOT NULL,
    ask DOUBLE NOT NULL,
    bid DOUBLE NOT NULL,
    base_currency_id INT NOT NULL,
    CONSTRAINT base_currency_id_ticks
	    FOREIGN KEY (base_currency_id)
	    REFERENCES currency(id)
	    ON UPDATE CASCADE ON DELETE RESTRICT,
    quote_currency_id INT NOT NULL,
    CONSTRAINT quote_currency_id_ticks
	    FOREIGN KEY (quote_currency_id)
	    REFERENCES currency(id)
	    ON UPDATE CASCADE ON DELETE RESTRICT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
	updated_at TIMESTAMP NULL
);

