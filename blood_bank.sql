-- ============================================================
--  BLOOD BANK MANAGEMENT SYSTEM — SQLite Schema
-- ============================================================

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- ------------------------------------------------------------
-- TABLE: Donors
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Donors (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    blood_type    TEXT    NOT NULL CHECK (blood_type IN ('A+','A-','B+','B-','AB+','AB-','O+','O-')),
    contact       TEXT    NOT NULL UNIQUE,
    location      TEXT    NOT NULL,
    is_eligible   INTEGER NOT NULL DEFAULT 1 CHECK (is_eligible IN (0, 1)),
    last_donated  DATE,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
-- TABLE: Inventory
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Inventory (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    blood_type    TEXT    NOT NULL CHECK (blood_type IN ('A+','A-','B+','B-','AB+','AB-','O+','O-')),
    units         INTEGER NOT NULL CHECK (units >= 0),
    expiry_date   DATE    NOT NULL,
    donor_id      INTEGER REFERENCES Donors(id) ON DELETE SET NULL,
    status        TEXT    NOT NULL DEFAULT 'available'
                          CHECK (status IN ('available', 'reserved', 'expired', 'used')),
    added_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
-- TABLE: Hospitals  (lookup table for Requests)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Hospitals (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL UNIQUE,
    location      TEXT    NOT NULL,
    contact       TEXT
);

-- ------------------------------------------------------------
-- TABLE: Requests
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Requests (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    hospital_id     INTEGER NOT NULL REFERENCES Hospitals(id) ON DELETE RESTRICT,
    hospital_name   TEXT    NOT NULL,          -- denormalized for quick reads
    blood_type      TEXT    NOT NULL CHECK (blood_type IN ('A+','A-','B+','B-','AB+','AB-','O+','O-')),
    units_needed    INTEGER NOT NULL DEFAULT 1 CHECK (units_needed > 0),
    urgency_level   TEXT    NOT NULL DEFAULT 'normal'
                            CHECK (urgency_level IN ('critical','high','normal','low')),
    location        TEXT    NOT NULL,
    status          TEXT    NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending','fulfilled','cancelled')),
    request_date    DATE    NOT NULL DEFAULT (DATE('now')),
    fulfilled_date  DATE,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
-- TABLE: Donations  (tracks each donor → inventory event)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Donations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    donor_id      INTEGER NOT NULL REFERENCES Donors(id) ON DELETE CASCADE,
    inventory_id  INTEGER NOT NULL REFERENCES Inventory(id) ON DELETE CASCADE,
    donation_date DATE    NOT NULL DEFAULT (DATE('now')),
    notes         TEXT
);

-- ------------------------------------------------------------
-- TABLE: Fulfillments  (links Requests → Inventory units used)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Fulfillments (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id    INTEGER NOT NULL REFERENCES Requests(id) ON DELETE CASCADE,
    inventory_id  INTEGER NOT NULL REFERENCES Inventory(id) ON DELETE RESTRICT,
    units_used    INTEGER NOT NULL CHECK (units_used > 0),
    fulfilled_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
--  INDEXES
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_donors_blood_type    ON Donors(blood_type);
CREATE INDEX IF NOT EXISTS idx_inventory_blood_type ON Inventory(blood_type);
CREATE INDEX IF NOT EXISTS idx_inventory_status     ON Inventory(status);
CREATE INDEX IF NOT EXISTS idx_inventory_expiry     ON Inventory(expiry_date);
CREATE INDEX IF NOT EXISTS idx_requests_blood_type  ON Requests(blood_type);
CREATE INDEX IF NOT EXISTS idx_requests_urgency     ON Requests(urgency_level);
CREATE INDEX IF NOT EXISTS idx_requests_status      ON Requests(status);

-- ============================================================
--  VIEWS
-- ============================================================

-- Available blood stock summary
CREATE VIEW IF NOT EXISTS v_blood_stock AS
SELECT
    blood_type,
    SUM(units)          AS total_units,
    COUNT(*)            AS bag_count,
    MIN(expiry_date)    AS earliest_expiry
FROM Inventory
WHERE status = 'available'
  AND expiry_date >= DATE('now')
GROUP BY blood_type;

-- Open (pending) requests ranked by urgency
CREATE VIEW IF NOT EXISTS v_open_requests AS
SELECT
    r.id,
    r.hospital_name,
    r.blood_type,
    r.units_needed,
    r.urgency_level,
    r.location,
    r.request_date,
    CASE r.urgency_level
        WHEN 'critical' THEN 1
        WHEN 'high'     THEN 2
        WHEN 'normal'   THEN 3
        WHEN 'low'      THEN 4
    END AS priority_rank
FROM Requests r
WHERE r.status = 'pending'
ORDER BY priority_rank, r.request_date;

-- ============================================================
--  TRIGGERS
-- ============================================================

-- Auto-expire inventory bags past their expiry date
CREATE TRIGGER IF NOT EXISTS trg_expire_inventory
AFTER UPDATE OF status ON Inventory
BEGIN
    UPDATE Inventory
    SET status = 'expired'
    WHERE status = 'available'
      AND expiry_date < DATE('now');
END;

-- Mark a request fulfilled when all needed units are assigned
CREATE TRIGGER IF NOT EXISTS trg_auto_fulfill_request
AFTER INSERT ON Fulfillments
BEGIN
    UPDATE Requests
    SET status         = 'fulfilled',
        fulfilled_date = DATE('now')
    WHERE id = NEW.request_id
      AND units_needed <= (
          SELECT COALESCE(SUM(units_used), 0)
          FROM Fulfillments
          WHERE request_id = NEW.request_id
      );
END;

-- ============================================================
--  SAMPLE DATA — Hospitals
-- ============================================================
INSERT INTO Hospitals (name, location, contact) VALUES
    ('City General Hospital',       'Mumbai, MH',    '+91-22-10001111'),
    ('Apollo Multispecialty',       'Delhi, DL',     '+91-11-20002222'),
    ('Fortis Healthcare',           'Bengaluru, KA', '+91-80-30003333'),
    ('AIIMS Trauma Centre',         'Delhi, DL',     '+91-11-40004444'),
    ('Kokilaben Dhirubhai Ambani',  'Mumbai, MH',    '+91-22-50005555');

-- ============================================================
--  SAMPLE DATA — Donors
-- ============================================================
INSERT INTO Donors (name, blood_type, contact, location, last_donated) VALUES
    ('Arjun Mehta',      'O+',  '+91-9800001111', 'Mumbai, MH',    '2025-12-10'),
    ('Priya Sharma',     'A+',  '+91-9800002222', 'Delhi, DL',     '2026-01-15'),
    ('Ravi Kumar',       'B+',  '+91-9800003333', 'Bengaluru, KA', '2025-11-20'),
    ('Sneha Iyer',       'AB-', '+91-9800004444', 'Chennai, TN',   '2026-02-05'),
    ('Karan Singh',      'O-',  '+91-9800005555', 'Jaipur, RJ',    '2026-03-01'),
    ('Meera Nair',       'A-',  '+91-9800006666', 'Kochi, KL',     '2025-10-18'),
    ('Deepak Verma',     'B-',  '+91-9800007777', 'Lucknow, UP',   '2026-01-28'),
    ('Ananya Ghosh',     'AB+', '+91-9800008888', 'Kolkata, WB',   '2026-02-20'),
    ('Vijay Patel',      'O+',  '+91-9800009999', 'Ahmedabad, GJ', '2025-12-30'),
    ('Lakshmi Reddy',    'A+',  '+91-9800010101', 'Hyderabad, TS', '2026-03-10');

-- ============================================================
--  SAMPLE DATA — Inventory
-- ============================================================
INSERT INTO Inventory (blood_type, units, expiry_date, donor_id, status) VALUES
    ('O+',  5, '2026-07-01', 1,  'available'),
    ('A+',  3, '2026-06-15', 2,  'available'),
    ('B+',  4, '2026-07-20', 3,  'available'),
    ('AB-', 2, '2026-05-30', 4,  'available'),
    ('O-',  6, '2026-08-10', 5,  'available'),
    ('A-',  2, '2026-06-05', 6,  'available'),
    ('B-',  1, '2026-05-25', 7,  'available'),
    ('AB+', 3, '2026-07-15', 8,  'available'),
    ('O+',  4, '2026-06-28', 9,  'available'),
    ('A+',  5, '2026-08-01', 10, 'available'),
    ('O-',  2, '2026-04-20', 5,  'available'),   -- expiring soon
    ('B+',  1, '2026-05-10', 3,  'reserved'),
    ('A+',  2, '2025-12-01', 2,  'expired');     -- already expired

-- ============================================================
--  SAMPLE DATA — Requests
-- ============================================================
INSERT INTO Requests (hospital_id, hospital_name, blood_type, units_needed, urgency_level, location, request_date, status) VALUES
    (1, 'City General Hospital',      'O-',  3, 'critical', 'Mumbai, MH',    '2026-04-17', 'pending'),
    (2, 'Apollo Multispecialty',      'A+',  2, 'high',     'Delhi, DL',     '2026-04-16', 'pending'),
    (3, 'Fortis Healthcare',          'B+',  1, 'normal',   'Bengaluru, KA', '2026-04-15', 'pending'),
    (4, 'AIIMS Trauma Centre',        'AB-', 2, 'critical', 'Delhi, DL',     '2026-04-17', 'pending'),
    (5, 'Kokilaben Dhirubhai Ambani', 'O+',  4, 'high',     'Mumbai, MH',    '2026-04-14', 'fulfilled'),
    (1, 'City General Hospital',      'A-',  1, 'low',      'Mumbai, MH',    '2026-04-13', 'fulfilled'),
    (2, 'Apollo Multispecialty',      'B-',  1, 'normal',   'Delhi, DL',     '2026-04-12', 'cancelled');

-- ============================================================
--  SAMPLE DATA — Donations
-- ============================================================
INSERT INTO Donations (donor_id, inventory_id, donation_date) VALUES
    (1, 1,  '2026-04-01'),
    (2, 2,  '2026-04-02'),
    (3, 3,  '2026-04-03'),
    (4, 4,  '2026-04-04'),
    (5, 5,  '2026-04-05'),
    (6, 6,  '2026-04-06'),
    (7, 7,  '2026-04-07'),
    (8, 8,  '2026-04-08'),
    (9, 9,  '2026-04-09'),
    (10, 10,'2026-04-10');

-- ============================================================
--  SAMPLE DATA — Fulfillments
-- ============================================================
INSERT INTO Fulfillments (request_id, inventory_id, units_used) VALUES
    (5, 1, 4),   -- Kokilaben O+ request fulfilled from inventory #1
    (6, 6, 1);   -- City General A- request fulfilled from inventory #6

