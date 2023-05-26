USE db_forex;

INSERT INTO currency(nom, iso_code)
VALUES
('United States dollar', 'USD'),
('Euro', 'EUR'),
('Pound sterling', 'GBP'),
('Japanese yen', 'JPY'),
('Australian dollar', 'AUD'),
('New Zealand dollar', 'NZD'),
('Swiss franc', 'CHF'),
('Canadian dollar', 'CAD');

INSERT INTO country(nom, currency_id)
VALUES
('United States', 1),
('Austria', 2),
('Belgium', 2),
('Croatia', 2),
('Cyprus', 2),
('Estonia', 2),
('Finland', 2),
('France', 2),
('Germany', 2),
('Greece', 2),
('Ireland', 2),
('Italy', 2),
('Latvia', 2),
('Lithuania', 2),
('Luxembourg', 2),
('Malta', 2),
('Netherlands', 2),
('Portugal', 2),
('Slovakia', 2),
('Slovenia', 2),
('Spain', 2),
('United Kingdom', 3),
('Japan', 4),
('Australia', 5),
('New Zealand', 6),
('Switzerland', 7),
('Canada', 8);


