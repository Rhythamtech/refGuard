-- Optimized Database Schema for Customer,Refund & Fraud Management System
CREATE TABLE `customer` (
  `id` integer PRIMARY KEY,
  `full_name` varchar(255) NOT NULL,
  `email` varchar(255) UNIQUE NOT NULL,
  `phone_number` varchar(255),
  `address` text,
  `password_hash` varchar(255) NOT NULL,
  `created_at` timestamp DEFAULT (now ()),
  `updated_at` timestamp DEFAULT (now ())
);

CREATE TABLE `products` (
  `id` integer PRIMARY KEY,
  `title` varchar(255) NOT NULL,
  `description` text,
  `category` varchar(255) NOT NULL,
  `subcategory` varchar(255),
  `price` decimal(10, 2) NOT NULL,
  `is_returnable` boolean DEFAULT true,
  `return_window_days` integer DEFAULT 30,
  `created_at` timestamp DEFAULT (now ()),
  `updated_at` timestamp DEFAULT (now ())
);

CREATE TABLE `orders` (
  `id` integer PRIMARY KEY,
  `ordered_at` timestamp DEFAULT (now ()),
  `customer_id` integer,
  `status` varchar(255) NOT NULL,
  `total_amount` decimal(10, 2) NOT NULL,
  `shipping_address` text NOT NULL,
  `payment_method` varchar(255),
  `delivered_at` timestamp
);

CREATE TABLE `order_items` (
  `id` integer PRIMARY KEY,
  `order_id` integer,
  `product_id` integer,
  `quantity` integer NOT NULL,
  `unit_price` decimal(10, 2) NOT NULL,
  `total_price` decimal(10, 2) NOT NULL,
  `item_status` varchar(255) NOT NULL
);

CREATE TABLE `refund_request` (
  `id` integer PRIMARY KEY,
  `customer_id` integer,
  `order_item_id` integer,
  `reason` text NOT NULL,
  `reason_category` varchar(255) NOT NULL,
  `attachment_url` varchar(255),
  `status` varchar(255) NOT NULL DEFAULT 'pending',
  `requested_refund_amount` decimal(10, 2) NOT NULL,
  `created_at` timestamp DEFAULT (now ()),
  `resolved_at` timestamp
);

CREATE TABLE `refund_decision` (
  `id` integer PRIMARY KEY,
  `refund_request_id` integer,
  `decision` varchar(255) NOT NULL,
  `decision_by` integer,
  `refunded_amount` decimal(10, 2) DEFAULT 0,
  `review` text,
  `created_at` timestamp DEFAULT (now ()),
  `decided_at` timestamp
);

CREATE TABLE `fraud_history` (
  `id` integer PRIMARY KEY,
  `refund_request_id` integer,
  `fraud_score` decimal(5, 2) NOT NULL,
  `flagged_rules` text,
  `created_at` timestamp DEFAULT (now ())
);

CREATE TABLE `admin_user` (
  `id` integer PRIMARY KEY,
  `name` varchar(255) NOT NULL,
  `email` varchar(255) UNIQUE NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `role` varchar(255) NOT NULL,
  `last_login` timestamp,
  `created_at` timestamp DEFAULT (now ())
);

-- Commenting this because will run only once in Prod Database
-- ALTER TABLE `orders` ADD FOREIGN KEY (`customer_id`) REFERENCES `customer` (`id`);
-- ALTER TABLE `order_items` ADD FOREIGN KEY (`order_id`) REFERENCES `orders` (`id`);
-- ALTER TABLE `order_items` ADD FOREIGN KEY (`product_id`) REFERENCES `products` (`id`);
-- ALTER TABLE `refund_request` ADD FOREIGN KEY (`customer_id`) REFERENCES `customer` (`id`);
-- ALTER TABLE `refund_request` ADD FOREIGN KEY (`order_item_id`) REFERENCES `order_items` (`id`);
-- ALTER TABLE `refund_decision` ADD FOREIGN KEY (`refund_request_id`) REFERENCES `refund_request` (`id`);
-- ALTER TABLE `refund_decision` ADD FOREIGN KEY (`decision_by`) REFERENCES `admin_user` (`id`);
-- ALTER TABLE `fraud_history` ADD FOREIGN KEY (`refund_request_id`) REFERENCES `refund_request` (`id`);
-- 1. INSERT MOCK CUSTOMERS (15 Indian Users)
INSERT INTO
  customer (
    id,
    full_name,
    email,
    phone_number,
    address,
    password_hash,
    created_at,
    updated_at
  )
VALUES
  (
    1,
    'Aarav Sharma',
    'aarav.sharma@gmail.com',
    '+91 98765 43210',
    'A-404, Shanti Apartments, Sector 12, Dwarka, New Delhi - 110075',
    '74d64b6f5ba84d9726941a1cea795cfe',
    '2026-01-10 10:00:00',
    '2026-01-10 10:00:00'
  ),
  (
    2,
    'Priya Patel',
    'priya.patel@yahoo.com',
    '+91 98234 56789',
    'Plot No 42, Vasant Vihar, Ahmedabad, Gujarat - 380015',
    '148b8b40587019fcba3e1dd8794becab',
    '2026-01-12 14:30:00',
    '2026-01-12 14:30:00'
  ),
  (
    3,
    'Rajesh Iyer',
    'rajesh.iyer@outlook.com',
    '+91 97456 12308',
    '12, 3rd Main Road, Kasturi Nagar, Bengaluru, Karnataka - 560043',
    'c1cb5c2c1eabbb0707c85e03bf5662f6',
    '2026-01-15 09:15:00',
    '2026-01-15 09:15:00'
  ),
  (
    4,
    'Sunita Reddy',
    'sunita.reddy@gmail.com',
    '+91 96123 45670',
    'H.No. 8-2-293/82, Jubilee Hills, Hyderabad, Telangana - 500033',
    '2d8def0a5f0966153e2df3e5e3e4ecf0',
    '2026-01-18 11:45:00',
    '2026-01-18 11:45:00'
  ),
  (
    5,
    'Vikram Singh',
    'vikram.singh@gmail.com',
    '+91 95345 67890',
    '24, Gandhi Nagar, Jaipur, Rajasthan - 302015',
    'f5eb9bb34aabc9d38a56ae47c8106473',
    '2026-01-20 16:20:00',
    '2026-01-20 16:20:00'
  ),
  (
    6,
    'Sneha Kulkarni',
    'sneha.k@hotmail.com',
    '+91 94234 56781',
    'Flat 302, Rohan Heights, Erandwane, Pune, Maharashtra - 411004',
    '4a2db27b9f04a0b61c9f81b1af6d9e9d',
    '2026-01-22 08:30:00',
    '2026-01-22 08:30:00'
  ),
  (
    7,
    'Rohan Das',
    'rohan.das@gmail.com',
    '+91 93123 45672',
    'Block C, Salt Lake Sector 5, Kolkata, West Bengal - 700091',
    'c683382092ee53204ebe878e180dc906',
    '2026-01-25 12:00:00',
    '2026-01-25 12:00:00'
  ),
  (
    8,
    'Anjali Nair',
    'anjali.nair@live.com',
    '+91 92123 45673',
    'T-3, Pearl Castle, Pattom, Trivandrum, Kerala - 695004',
    '79da873265de98059d0b058ef62be2ce',
    '2026-01-28 15:10:00',
    '2026-01-28 15:10:00'
  ),
  (
    9,
    'Amit Verma',
    'amit.verma@gmail.com',
    '+91 91123 45674',
    '54/2, Hazratganj, Lucknow, Uttar Pradesh - 226001',
    '70b009431383ffd7590a842e8dc19fe7',
    '2026-02-01 10:40:00',
    '2026-02-01 10:40:00'
  ),
  (
    10,
    'Deepika Sen',
    'deepika.sen@gmail.com',
    '+91 90123 45675',
    '701, Marina Towers, Bandra West, Mumbai, Maharashtra - 400050',
    'bb4dd31e8ef1f7f7ec3006b627203e11',
    '2026-02-03 17:55:00',
    '2026-02-03 17:55:00'
  ),
  (
    11,
    'Manish Joshi',
    'manish.joshi@rediffmail.com',
    '+91 89123 45676',
    'G-12, Arera Colony, Bhopal, Madhya Pradesh - 462016',
    '70d96c7cc60248fc623dd8c320b1dd73',
    '2026-02-05 09:00:00',
    '2026-02-05 09:00:00'
  ),
  (
    12,
    'Neha Bhatia',
    'neha.bhatia@gmail.com',
    '+91 88123 45677',
    '15, Mall Road, Amritsar, Punjab - 143001',
    'f01b03fc71cc3e3a77ab08beca1223aa',
    '2026-02-08 14:15:00',
    '2026-02-08 14:15:00'
  ),
  (
    13,
    'Siddharth Kapoor',
    'siddharth.k@gmail.com',
    '+91 87123 45678',
    '32, Rajpur Road, Dehradun, Uttarakhand - 248001',
    '9e54bb0bbff3d312705336a7b76c605c',
    '2026-02-10 11:30:00',
    '2026-02-10 11:30:00'
  ),
  (
    14,
    'Pooja Hegde',
    'pooja.hegde@gmail.com',
    '+91 86123 45679',
    'Flat 101, Prestige Residency, Mangalore, Karnataka - 575001',
    '12796ed8da8e177e0183caae8eb87657',
    '2026-02-12 13:00:00',
    '2026-02-12 13:00:00'
  ),
  (
    15,
    'Rahul Bose',
    'rahul.bose@gmail.com',
    '+91 85123 45680',
    '4B, Southern Avenue, Kolkata, West Bengal - 700029',
    '6beade64100bfa1b2088bd997e204fbd',
    '2026-02-15 16:45:00',
    '2026-02-15 16:45:00'
  );

-- 2. INSERT MOCK ADMIN USERS (3 Records)
INSERT INTO
  admin_user (
    id,
    name,
    email,
    password_hash,
    role,
    last_login,
    created_at
  )
VALUES
  (
    1,
    'Suresh Kumar',
    'suresh.admin@ecommerce.com',
    '1836def6c4602c40e9bd0981a20994bc',
    'admin',
    '2026-02-20 09:00:00',
    '2026-01-01 08:00:00'
  ),
  (
    2,
    'Meera Jasmine',
    'meera.supervisor@ecommerce.com',
    '2c07c6e298530ba7c49e1d4477682e4f',
    'supervisor',
    '2026-02-20 09:30:00',
    '2026-01-02 08:00:00'
  ),
  (
    3,
    'Vijay Raghavan',
    'vijay.agent@ecommerce.com',
    '83ad679c2ba806c328d366de5e027fb4',
    'agent',
    '2026-02-20 10:00:00',
    '2026-01-03 08:00:00'
  );

-- 3. INSERT MOCK PRODUCTS (26 Records across multiple categories & subcategories)
INSERT INTO
  products (
    id,
    title,
    description,
    category,
    subcategory,
    price,
    is_returnable,
    return_window_days,
    created_at,
    updated_at
  )
VALUES
  (
    1,
    'iPhone 15 Pro Max',
    'Apple iPhone 15 Pro Max 256GB Black Titanium',
    'Electronics',
    'Smartphones',
    140000.00,
    true,
    7,
    '2026-01-01 00:00:00',
    '2026-01-01 00:00:00'
  ),
  (
    2,
    'OnePlus Nord CE 3',
    'OnePlus Nord CE 3 Lite 5G 8GB RAM 128GB',
    'Electronics',
    'Smartphones',
    19999.00,
    true,
    7,
    '2026-01-01 00:00:00',
    '2026-01-01 00:00:00'
  ),
  (
    3,
    'Boat Rockerz 450',
    'Boat Rockerz 450 Bluetooth On-Ear Headphones',
    'Electronics',
    'Audio',
    1499.00,
    true,
    10,
    '2026-01-01 00:00:00',
    '2026-01-01 00:00:00'
  ),
  (
    4,
    'Sony WH-1000XM5',
    'Sony WH-1000XM5 Wireless Noise Cancelling Headphones',
    'Electronics',
    'Audio',
    29990.00,
    true,
    10,
    '2026-01-01 00:00:00',
    '2026-01-01 00:00:00'
  ),
  (
    5,
    'Noise ColorFit Pulse',
    'Noise ColorFit Pulse 2 Max Smartwatch',
    'Electronics',
    'Smartwatches',
    1999.00,
    true,
    7,
    '2026-01-01 00:00:00',
    '2026-01-01 00:00:00'
  ),
  (
    6,
    'Levis Men Straight Fit Jeans',
    'Levis Mens 511 Slim Fit Jeans',
    'Apparel',
    'Mens Wear',
    2599.00,
    true,
    30,
    '2026-01-01 00:00:00',
    '2026-01-01 00:00:00'
  ),
  (
    7,
    'Peter England Formal Shirt',
    'Peter England Mens Cotton Blend Formal Shirt',
    'Apparel',
    'Mens Wear',
    1299.00,
    true,
    30,
    '2026-01-01 00:00:00',
    '2026-01-01 00:00:00'
  ),
  (
    8,
    'Biba Women Kurta Set',
    'Biba Women Printed Cotton Kurta with Palazzo Set',
    'Apparel',
    'Womens Wear',
    3499.00,
    true,
    30,
    '2026-01-01 00:00:00',
    '2026-01-01 00:00:00'
  ),
  (
    9,
    'Aurelia Cotton Kurti',
    'Aurelia Women Solid Cotton Straight Kurti',
    'Apparel',
    'Womens Wear',
    899.00,
    true,
    30,
    '2026-01-01 00:00:00',
    '2026-01-01 00:00:00'
  ),
  (
    10,
    'Nike Air Max Sneakers',
    'Nike Mens Air Max Shoes',
    'Apparel',
    'Footwear',
    8999.00,
    true,
    14,
    '2026-01-01 00:00:00',
    '2026-01-01 00:00:00'
  ),
  (
    11,
    'Prestige Omega Cookware Set',
    'Prestige Omega Deluxe Granite Cookware Set, 3 Pieces',
    'Home & Kitchen',
    'Cookware',
    3299.00,
    true,
    10,
    '2026-01-01 00:00:00',
    '2026-01-01 00:00:00'
  ),
  (
    12,
    'Pigeon Non-Stick Kadai',
    'Pigeon Non-Stick Flat Tawa and Kadai Set',
    'Home & Kitchen',
    'Cookware',
    1199.00,
    true,
    10,
    '2026-01-01 00:00:00',
    '2026-01-01 00:00:00'
  ),
  (
    13,
    'Philips Air Fryer HD9200',
    'Philips Daily Collection Air Fryer 4.1L',
    'Home & Kitchen',
    'Appliances',
    6999.00,
    true,
    10,
    '2026-01-01 00:00:00',
    '2026-01-01 00:00:00'
  ),
  (
    14,
    'Kent Grand Water Purifier',
    'Kent Grand RO+UV+UF Water Purifier 8L',
    'Home & Kitchen',
    'Appliances',
    16500.00,
    true,
    10,
    '2026-01-01 00:00:00',
    '2026-01-01 00:00:00'
  ),
  (
    15,
    'The Alchemist',
    'The Alchemist by Paulo Coelho Paperback',
    'Books',
    'Fiction',
    299.00,
    true,
    30,
    '2026-01-01 00:00:00',
    '2026-01-01 00:00:00'
  ),
  (
    16,
    'Atomic Habits',
    'Atomic Habits by James Clear Hardcover',
    'Books',
    'Non-Fiction',
    450.00,
    true,
    30,
    '2026-01-01 00:00:00',
    '2026-01-01 00:00:00'
  ),
  (
    17,
    'Sapiens',
    'Sapiens: A Brief History of Humankind',
    'Books',
    'Non-Fiction',
    399.00,
    true,
    30,
    '2026-01-01 00:00:00',
    '2026-01-01 00:00:00'
  ),
  (
    18,
    'Harry Potter Set',
    'Harry Potter Complete Book Set 1-7',
    'Books',
    'Fiction',
    2499.00,
    true,
    30,
    '2026-01-01 00:00:00',
    '2026-01-01 00:00:00'
  ),
  (
    19,
    'Mamaearth Onion Hair Oil',
    'Mamaearth Onion Hair Oil with Booster for Hair Fall Control 150ml',
    'Beauty & Personal Care',
    'Haircare',
    419.00,
    false,
    0,
    '2026-01-01 00:00:00',
    '2026-01-01 00:00:00'
  ),
  (
    20,
    'The Derma Co 10% Niacinamide Serum',
    'The Derma Co 10% Niacinamide Face Serum for Acne Marks 30ml',
    'Beauty & Personal Care',
    'Skincare',
    599.00,
    false,
    0,
    '2026-01-01 00:00:00',
    '2026-01-01 00:00:00'
  ),
  (
    21,
    'L''Oreal Paris Shampoo',
    'L''Oreal Paris Total Repair 5 Shampoo 650ml',
    'Beauty & Personal Care',
    'Haircare',
    649.00,
    false,
    0,
    '2026-01-01 00:00:00',
    '2026-01-01 00:00:00'
  ),
  (
    22,
    'Nivea Soft Cream',
    'Nivea Soft Light Moisturiser Cream 300ml',
    'Beauty & Personal Care',
    'Skincare',
    349.00,
    false,
    0,
    '2026-01-01 00:00:00',
    '2026-01-01 00:00:00'
  ),
  (
    23,
    'Logitech Wireless Mouse',
    'Logitech B170 Wireless Mouse, 2.4 GHz',
    'Electronics',
    'Accessories',
    649.00,
    true,
    7,
    '2026-01-01 00:00:00',
    '2026-01-01 00:00:00'
  ),
  (
    24,
    'SanDisk 128GB Pen Drive',
    'SanDisk Ultra Dual Drive Luxe Type-C 128GB',
    'Electronics',
    'Accessories',
    1199.00,
    true,
    7,
    '2026-01-01 00:00:00',
    '2026-01-01 00:00:00'
  ),
  (
    25,
    'Milton Thermosteel Bottle',
    'Milton Thermosteel Duo Deluxe 1000ml Bottle',
    'Home & Kitchen',
    'Bottles',
    999.00,
    true,
    14,
    '2026-01-01 00:00:00',
    '2026-01-01 00:00:00'
  ),
  (
    26,
    'Wildcraft Backpack',
    'Wildcraft 35L Casual Waterproof Backpack',
    'Apparel',
    'Accessories',
    1899.00,
    true,
    14,
    '2026-01-01 00:00:00',
    '2026-01-01 00:00:00'
  );

-- 4. INSERT MOCK ORDERS (17 Orders linked to Indian customers)
INSERT INTO
  orders (
    id,
    ordered_at,
    customer_id,
    status,
    total_amount,
    shipping_address,
    payment_method,
    delivered_at
  )
VALUES
  (
    1,
    '2026-02-01 11:00:00',
    1,
    'delivered',
    141499.00,
    'A-404, Shanti Apartments, Sector 12, Dwarka, New Delhi - 110075',
    'Credit Card',
    '2026-02-03 14:00:00'
  ),
  (
    2,
    '2026-02-02 10:30:00',
    2,
    'delivered',
    3499.00,
    'Plot No 42, Vasant Vihar, Ahmedabad, Gujarat - 380015',
    'COD',
    '2026-02-05 16:20:00'
  ),
  (
    3,
    '2026-02-03 12:15:00',
    3,
    'delivered',
    3299.00,
    '12, 3rd Main Road, Kasturi Nagar, Bengaluru, Karnataka - 560043',
    'PayPal',
    '2026-02-05 11:10:00'
  ),
  (
    4,
    '2026-02-04 15:45:00',
    4,
    'delivered',
    17196.00,
    'H.No. 8-2-293/82, Jubilee Hills, Hyderabad, Telangana - 500033',
    'Credit Card',
    '2026-02-06 13:30:00'
  ),
  (
    5,
    '2026-02-05 14:00:00',
    5,
    'delivered',
    19999.00,
    '24, Gandhi Nagar, Jaipur, Rajasthan - 302015',
    'COD',
    '2026-02-08 15:00:00'
  ),
  (
    6,
    '2026-02-06 09:30:00',
    6,
    'shipped',
    419.00,
    'Flat 302, Rohan Heights, Erandwane, Pune, Maharashtra - 411004',
    'Credit Card',
    NULL
  ),
  (
    7,
    '2026-02-07 16:00:00',
    7,
    'delivered',
    1499.00,
    'Block C, Salt Lake Sector 5, Kolkata, West Bengal - 700091',
    'PayPal',
    '2026-02-10 12:00:00'
  ),
  (
    8,
    '2026-02-08 11:20:00',
    8,
    'cancelled',
    399.00,
    'T-3, Pearl Castle, Pattom, Trivandrum, Kerala - 695004',
    'Credit Card',
    NULL
  ),
  (
    9,
    '2026-02-09 13:45:00',
    9,
    'delivered',
    2599.00,
    '54/2, Hazratganj, Lucknow, Uttar Pradesh - 226001',
    'COD',
    '2026-02-12 11:00:00'
  ),
  (
    10,
    '2026-02-10 18:30:00',
    10,
    'delivered',
    29990.00,
    '701, Marina Towers, Bandra West, Mumbai, Maharashtra - 400050',
    'Credit Card',
    '2026-02-12 14:20:00'
  ),
  (
    11,
    '2026-02-11 10:15:00',
    11,
    'delivered',
    1199.00,
    'G-12, Arera Colony, Bhopal, Madhya Pradesh - 462016',
    'COD',
    '2026-02-14 16:40:00'
  ),
  (
    12,
    '2026-02-12 14:50:00',
    12,
    'ordered',
    450.00,
    '15, Mall Road, Amritsar, Punjab - 143001',
    'Credit Card',
    NULL
  ),
  (
    13,
    '2026-02-13 11:10:00',
    13,
    'delivered',
    2198.00,
    '32, Rajpur Road, Dehradun, Uttarakhand - 248001',
    'PayPal',
    '2026-02-15 13:00:00'
  ),
  (
    14,
    '2026-02-14 09:00:00',
    14,
    'delivered',
    1299.00,
    'Flat 101, Prestige Residency, Mangalore, Karnataka - 575001',
    'Credit Card',
    '2026-02-16 10:30:00'
  ),
  (
    15,
    '2026-02-15 15:30:00',
    15,
    'delivered',
    1899.00,
    '4B, Southern Avenue, Kolkata, West Bengal - 700029',
    'COD',
    '2026-02-17 12:15:00'
  ),
  (
    16,
    '2026-02-16 10:00:00',
    1,
    'delivered',
    899.00,
    'A-404, Shanti Apartments, Sector 12, Dwarka, New Delhi - 110075',
    'Credit Card',
    '2026-02-18 11:00:00'
  ),
  (
    17,
    '2026-02-17 14:20:00',
    2,
    'delivered',
    649.00,
    'Plot No 42, Vasant Vihar, Ahmedabad, Gujarat - 380015',
    'PayPal',
    '2026-02-19 15:30:00'
  );

-- 5. INSERT MOCK ORDER ITEMS
INSERT INTO
  order_items (
    id,
    order_id,
    product_id,
    quantity,
    unit_price,
    total_price,
    item_status
  )
VALUES
  (1, 1, 1, 1, 140000.00, 140000.00, 'delivered'),
  (2, 1, 3, 1, 1499.00, 1499.00, 'refunded'),
  (3, 2, 8, 1, 3499.00, 3499.00, 'delivered'),
  (4, 3, 11, 1, 3299.00, 3299.00, 'refunded'),
  (5, 4, 13, 1, 6999.00, 6999.00, 'delivered'),
  (6, 4, 10, 1, 8999.00, 8999.00, 'delivered'),
  (7, 4, 20, 2, 599.00, 1198.00, 'delivered'),
  (8, 5, 2, 1, 19999.00, 19999.00, 'delivered'),
  (9, 6, 19, 1, 419.00, 419.00, 'delivered'),
  (10, 7, 3, 1, 1499.00, 1499.00, 'pending_return'),
  (11, 8, 17, 1, 399.00, 399.00, 'cancelled'),
  (12, 9, 6, 1, 2599.00, 2599.00, 'delivered'),
  (13, 10, 4, 1, 29990.00, 29990.00, 'delivered'),
  (14, 11, 12, 1, 1199.00, 1199.00, 'delivered'),
  (15, 12, 16, 1, 450.00, 450.00, 'ordered'),
  (16, 13, 24, 1, 1199.00, 1199.00, 'delivered'),
  (17, 13, 25, 1, 999.00, 999.00, 'refunded'),
  (18, 14, 7, 1, 1299.00, 1299.00, 'delivered'),
  (19, 15, 26, 1, 1899.00, 1899.00, 'delivered'),
  (20, 16, 9, 1, 899.00, 899.00, 'delivered'),
  (21, 17, 23, 1, 649.00, 649.00, 'delivered');

-- 6. INSERT REFUND REQUESTS (6 Requests mapped to various reasons & statuses)
INSERT INTO
  refund_request (
    id,
    customer_id,
    order_item_id,
    reason,
    reason_category,
    attachment_url,
    status,
    requested_refund_amount,
    created_at,
    resolved_at
  )
VALUES
  (
    1,
    1,
    2,
    'The right side speaker of the headphone has no audio output.',
    'damaged',
    'https://store2.gofile.io/download/web/c6f049eb-3e34-4acc-8087-704482dbe32a/image.jpeg',
    'approved',
    1499.00,
    '2026-02-04 10:00:00',
    '2026-02-04 10:15:00'
  ),
  (
    2,
    3,
    4,
    'The glass lid was shattered upon arrival. Kindly refund.',
    'damaged',
    'https://store-eu-par-6.gofile.io/download/web/cc258efd-59ec-4215-b994-21f34f841901/image.png',
    'approved',
    3299.00,
    '2026-02-06 09:30:00',
    '2026-02-07 11:45:00'
  ),
  (
    3,
    4,
    7,
    'Changed my mind, do not want this cosmetic item anymore.',
    'cancel_order',
    NULL,
    'rejected',
    599.00,
    '2026-02-07 14:00:00',
    '2026-02-07 16:30:00'
  ),
  (
    4,
    10,
    13,
    'Did not receive the package although status claims delivered.',
    'not_delivered',
    NULL,
    'escalated',
    29990.00,
    '2026-02-13 19:00:00',
    NULL
  ),
  (
    5,
    7,
    10,
    'Received a completely different item, looks like a cheap generic cable.',
    'wrong_item',
    'https://store2.gofile.io/download/web/c7977c03-64ee-461f-852f-dd334a45977c/image.jpeg',
    'pending',
    1499.00,
    '2026-02-11 15:00:00',
    NULL
  ),
  (
    6,
    13,
    17,
    'Color of the bottle is faded and has scratches on the bottom.',
    'quality',
    'https://store1.gofile.io/download/web/88bc2064-31bf-42b1-b545-77b2bf73f02f/image.jpeg',
    'approved',
    999.00,
    '2026-02-16 11:20:00',
    '2026-02-17 14:00:00'
  );

-- 7. INSERT REFUND DECISIONS (Linked directly to Request IDs, mapping resolutions & actors)
INSERT INTO
  refund_decision (
    id,
    refund_request_id,
    decision,
    decision_by,
    refunded_amount,
    review,
    created_at,
    decided_at
  )
VALUES
  (
    1,
    1,
    'approved',
    NULL,
    1499.00,
    'Automated refund process succeeded based on clear refund policy.',
    '2026-02-04 10:15:00',
    '2026-02-04 10:15:00'
  ),
  (
    2,
    2,
    'approved',
    3,
    3299.00,
    'Manual verification of broken glass lid attachment complete. Refund issued.',
    '2026-02-07 11:45:00',
    '2026-02-07 11:45:00'
  ),
  (
    3,
    3,
    'rejected',
    2,
    0.00,
    'Personal care / beauty items are non-returnable post-delivery. Request rejected.',
    '2026-02-07 16:30:00',
    '2026-02-07 16:30:00'
  ),
  (
    4,
    4,
    'pending_review',
    NULL,
    0.00,
    'Escalated due to high order value and suspicious location metadata.',
    '2026-02-13 19:05:00',
    NULL
  ),
  (
    5,
    6,
    'approved',
    3,
    999.00,
    'Scratches on metal body confirmed via photo upload. Approved partial/full refund.',
    '2026-02-17 14:00:00',
    '2026-02-17 14:00:00'
  );

-- 8. INSERT FRAUD HISTORY (Providing assessments and scores ranging 0.00 to 100.00)
INSERT INTO
  fraud_history (
    id,
    refund_request_id,
    fraud_score,
    flagged_rules,
    created_at
  )
VALUES
  (1, 1, 12.50, '[]', '2026-02-04 10:02:00'),
  (
    2,
    2,
    35.00,
    '["high_value_item"]',
    '2026-02-06 09:32:00'
  ),
  (
    3,
    3,
    60.00,
    '["non_returnable_item_claim", "quick_successive_returns"]',
    '2026-02-07 14:05:00'
  ),
  (
    4,
    4,
    92.50,
    '["high_value_item", "location_mismatch", "suspicious_not_delivered"]',
    '2026-02-13 19:02:00'
  ),
  (
    5,
    5,
    22.00,
    '["unverified_image_metadata"]',
    '2026-02-11 15:05:00'
  ),
  (6, 6, 8.40, '[]', '2026-02-16 11:22:00');