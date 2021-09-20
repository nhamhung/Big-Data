CREATE TABLE IF NOT EXISTS data (
  id INT NOT NULL,
  creation_date TIMESTAMP NOT NULL,
  sale_value INT NOT NULL,
  PRIMARY KEY (id)
);

INSERT INTO data (id, creation_date, sale_value) VALUES (0, '12-12-21', 1000);
INSERT INTO data (id, creation_date, sale_value) VALUES (1, '12-13-21', 2000);