-- init_db.sql — TravelBot Order Management Schema
-- Simplified to focus on order tracking use case

-- ── Orders Table ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS orders (
    order_id        VARCHAR(20) PRIMARY KEY,
    customer_name   VARCHAR(100) NOT NULL,
    status          VARCHAR(30)  NOT NULL,
    eta             VARCHAR(50),
    carrier         VARCHAR(50),
    origin          VARCHAR(50),
    destination     VARCHAR(50),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Optional: Order Items (if needed later) ───────────────────────────────
CREATE TABLE IF NOT EXISTS order_items (
    id          BIGSERIAL PRIMARY KEY,
    order_id    VARCHAR(20) NOT NULL,
    item_name   VARCHAR(100),
    quantity    INTEGER DEFAULT 1,
    price       NUMERIC(10,2),
    FOREIGN KEY (order_id) REFERENCES orders(order_id)
);

-- ── Seed Data (Order Tracking Example) ────────────────────────────────────
INSERT INTO orders (
    order_id,
    customer_name,
    status,
    eta,
    carrier,
    origin,
    destination
)
VALUES
    ('001', 'Priya Sharma',  'Shipped',    '5 Jun 2026', 'BlueDart', 'Mumbai',    'London'),
    ('002', 'Ravi Patel',    'Processing', '6 Jun 2026', 'DTDC',     'Singapore', 'Tokyo'),
    ('003', 'Aisha Mehta',   'Delivered',  'Already delivered', 'FedEx', 'Dubai', 'Paris'),
    ('004', 'James Liu',     'Shipped',    '7 Jun 2026', 'BlueDart', 'Delhi',     'Singapore'),
    ('005', 'Maria Santos',  'Processing', '8 Jun 2026', 'DTDC',     'Singapore', 'Tokyo')
ON CONFLICT (order_id) DO NOTHING;
