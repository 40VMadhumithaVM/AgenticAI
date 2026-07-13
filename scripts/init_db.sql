-- init_db.sql — Day 04 Ecombot seed schema

-- ── Orders ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS orders (
    order_id            VARCHAR(20)  PRIMARY KEY,
    customer_name       VARCHAR(100) NOT NULL,
    delivery_address    VARCHAR(50)  NOT NULL,
    delivery_date       DATE         NOT NULL,
    status              VARCHAR(20)  NOT NULL DEFAULT 'Confirmed',
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ── Products ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS products (
    product_id      VARCHAR(20)   PRIMARY KEY,
    product_name    VARCHAR(50)   NOT NULL,
    price_usd       NUMERIC(10,2) NOT NULL,
    stock           INTEGER       NOT NULL DEFAULT 100    
);

-- ── Conversation history ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS session_history (
    id          BIGSERIAL    PRIMARY KEY,
    session_id  VARCHAR(100) NOT NULL,
    user_id     VARCHAR(100) NOT NULL,
    role        VARCHAR(20)  NOT NULL,
    content     TEXT         NOT NULL,
    tool_calls  JSONB,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_sh_session ON session_history (session_id, created_at);

-- ── Order seed data ───────────────────────────────────────────────────────
INSERT INTO orders (order_id, customer_name, delivery_address, delivery_date, status)
VALUES
    ('ORD-1001', 'Priya Sharma',  'Chennai', '2026-07-15', 'Confirmed'),
    ('ORD-1002', 'Ravi Patel',    'Chennai', '2026-07-16', 'Out for delivery'),
    ('ORD-1003', 'Aisha Mehta',   'Chennai', '2026-07-16', 'Out for delivery'),
    ('ORD-1004', 'James Liu',     'Chennai', '2026-07-16', 'Cancelled'),    
    ('ORD-1005', 'Maria Santos',  'Chennai', '2026-07-16', 'Confirmed'),
    ('ORD-1006', 'Kenji Tanaka',  'Chennai', '2026-07-16', 'Confirmed'),
    ('ORD-1007', 'Fatima Al-Ali', 'Chennai', '2026-07-16', 'Confirmed')
ON CONFLICT (order_id) DO NOTHING;

-- ── Product seed data ─────────────────────────────────────────────────────
INSERT INTO products (product_id, product_name, price_usd, stock)
VALUES
    ('PR-201', 'Laptop',     500.00,  82),
    ('PR-202', 'Laptop',     400.00, 102),
    ('PR-203', 'Mobile',     150.00,  12),
    ('PR-204', 'Mobile',     200.00,  89),
    ('PR-205', 'Tablet',     300.00,  45),
    ('PR-206', 'Tablet',     250.00,  67),
    ('PR-207', 'Headphones',  50.00, 150),
    ('PR-208', 'Headphones',  80.00, 120),
    ('PR-209', 'Smartwatch', 120.00,  75),
    ('PR-210', 'Smartwatch', 100.00,  90)
ON CONFLICT (product_id) DO NOTHING;       
