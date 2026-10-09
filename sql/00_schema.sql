-- Generated from the loaded MySQL 8 model.

CREATE TABLE `dim_date` (
  `order_date` date DEFAULT NULL,
  `date_key` bigint NOT NULL,
  `year` int DEFAULT NULL,
  `month_number` int DEFAULT NULL,
  `month_key` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs DEFAULT NULL,
  `month_start` date DEFAULT NULL,
  `month_label` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs DEFAULT NULL,
  `day_of_month` int DEFAULT NULL,
  `day_name` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs DEFAULT NULL,
  `week_start` date DEFAULT NULL,
  `is_observed_date` int DEFAULT NULL,
  `is_complete_month` int DEFAULT NULL,
  PRIMARY KEY (`date_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_as_cs;

CREATE TABLE `dim_product` (
  `product_key` bigint NOT NULL,
  `sku` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs DEFAULT NULL,
  `style` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs DEFAULT NULL,
  `category` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs DEFAULT NULL,
  `size` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs DEFAULT NULL,
  `asin_count` int DEFAULT NULL,
  PRIMARY KEY (`product_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_as_cs;

CREATE TABLE `dim_geography` (
  `geography_key` bigint NOT NULL,
  `ship_city` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs DEFAULT NULL,
  `ship_state` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs DEFAULT NULL,
  `postal_code` varchar(6) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs DEFAULT NULL,
  `country` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs DEFAULT NULL,
  PRIMARY KEY (`geography_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_as_cs;

CREATE TABLE `dim_status` (
  `status_key` bigint NOT NULL,
  `status` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs DEFAULT NULL,
  `status_group` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs DEFAULT NULL,
  PRIMARY KEY (`status_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_as_cs;

CREATE TABLE `fact_order_lines` (
  `line_id` bigint NOT NULL,
  `source_index` bigint DEFAULT NULL,
  `order_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs DEFAULT NULL,
  `date_key` bigint DEFAULT NULL,
  `product_key` bigint DEFAULT NULL,
  `geography_key` bigint DEFAULT NULL,
  `status_key` bigint DEFAULT NULL,
  `fulfillment` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs DEFAULT NULL,
  `sales_channel` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs DEFAULT NULL,
  `shipping_service` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs DEFAULT NULL,
  `courier_status` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs DEFAULT NULL,
  `asin` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs DEFAULT NULL,
  `quantity` int DEFAULT NULL,
  `currency` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs DEFAULT NULL,
  `amount` decimal(12,2) DEFAULT NULL,
  `amount_minor` bigint DEFAULT NULL,
  `is_b2b` int DEFAULT NULL,
  `has_promotion` int DEFAULT NULL,
  `fulfilled_by` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs DEFAULT NULL,
  `is_duplicate_record` int DEFAULT NULL,
  `amount_missing` int DEFAULT NULL,
  `zero_quantity` int DEFAULT NULL,
  `is_sales_eligible` int DEFAULT NULL,
  `is_unvalued_shipped` int DEFAULT NULL,
  `order_valuation_complete` int DEFAULT NULL,
  `status_courier_conflict` int DEFAULT NULL,
  `geography_missing` int DEFAULT NULL,
  PRIMARY KEY (`line_id`),
  KEY `fk_fact_date_key` (`date_key`),
  KEY `fk_fact_product_key` (`product_key`),
  KEY `fk_fact_geography_key` (`geography_key`),
  KEY `fk_fact_status_key` (`status_key`),
  CONSTRAINT `fk_fact_date_key` FOREIGN KEY (`date_key`) REFERENCES `dim_date` (`date_key`),
  CONSTRAINT `fk_fact_geography_key` FOREIGN KEY (`geography_key`) REFERENCES `dim_geography` (`geography_key`),
  CONSTRAINT `fk_fact_product_key` FOREIGN KEY (`product_key`) REFERENCES `dim_product` (`product_key`),
  CONSTRAINT `fk_fact_status_key` FOREIGN KEY (`status_key`) REFERENCES `dim_status` (`status_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_as_cs;