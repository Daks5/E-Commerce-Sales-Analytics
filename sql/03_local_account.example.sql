-- For a NEW local installation, run with an administrator connection.
-- Replace the password placeholder locally before execution; never commit credentials.
-- This machine's scoped account is already configured; do not rerun unnecessarily.
CREATE DATABASE IF NOT EXISTS ecommerce_db
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs;
CREATE USER 'ecommerce_loader'@'localhost'
  IDENTIFIED BY 'REPLACE_LOCALLY_WITH_A_UNIQUE_PASSWORD';
GRANT ALL PRIVILEGES ON ecommerce_db.* TO 'ecommerce_loader'@'localhost';
