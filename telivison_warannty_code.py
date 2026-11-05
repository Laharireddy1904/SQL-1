"""
TELEVISION WARRANTY AND FAULT TRACKING


Measurement types:
    Nominal: display_technology
    Ordinal: fault_severity — Low < Medium < High
    Interval: manufacture_year
    Ratio: repair_duration_hours and repair_cost_pence

Composite primary keys:
    warranties: (unit_id, coverage_type)
    repair_actions: (report_id, action_sequence)

Deliberate imperfections:
    60 missing registration emails
    90 missing original fault descriptions
    18 extra duplicate fault reports
"""

import random
import sqlite3
import tempfile

from datetime import datetime, timedelta
from pathlib import Path
from google.colab import files


# ============================================================
# 1. Configuration
# ============================================================

SEED = 3398
rng = random.Random(SEED)

MODEL_COUNT = 40
UNIT_COUNT = 1200
TECHNICIAN_COUNT = 20
ORIGINAL_REPORT_COUNT = 1800
DUPLICATE_COUNT = 18

MISSING_EMAIL_COUNT = 60
MISSING_DESCRIPTION_COUNT = 90

OUTPUT_DIR = Path(
    tempfile.mkdtemp(prefix="television_", dir="/content")
)
DATABASE_PATH = OUTPUT_DIR / "television_warranty.db"


def iso(value):
    return value.strftime("%Y-%m-%d %H:%M:%S")


def date_check(column):
    return f"""
        length({column}) = 10
        AND {column} GLOB
            '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
        AND date({column}, '+0 days') IS NOT NULL
        AND date({column}, '+0 days') = {column}
    """


def timestamp_check(column):
    return f"""
        length({column}) = 19
        AND {column} GLOB
            '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9] [0-9][0-9]:[0-9][0-9]:[0-9][0-9]'
        AND datetime({column}, '+0 days') IS NOT NULL
        AND datetime({column}, '+0 days') = {column}
    """


# ============================================================
# 2. Schema
# ============================================================

SCHEMA = f"""
CREATE TABLE television_models (
    model_id INTEGER PRIMARY KEY,
    model_name TEXT NOT NULL UNIQUE
        CHECK (length(trim(model_name)) > 0),
    brand_name TEXT NOT NULL
        CHECK (length(trim(brand_name)) > 0),
    display_technology TEXT NOT NULL
        CHECK (display_technology IN ('LCD', 'QLED', 'OLED')),
    screen_size_inches REAL NOT NULL
        CHECK (
            typeof(screen_size_inches) IN ('integer', 'real')
            AND screen_size_inches BETWEEN 20 AND 100
        ),
    launch_year INTEGER NOT NULL
        CHECK (
            typeof(launch_year) = 'integer'
            AND launch_year BETWEEN 2000 AND 2030
        )
);

CREATE TABLE registered_units (
    unit_id INTEGER PRIMARY KEY,
    model_id INTEGER NOT NULL,
    serial_number TEXT NOT NULL UNIQUE
        CHECK (length(trim(serial_number)) > 0),
    manufacture_year INTEGER NOT NULL
        CHECK (typeof(manufacture_year) = 'integer'),
    manufactured_on TEXT NOT NULL
        CHECK ({date_check('manufactured_on')}),
    purchased_on TEXT NOT NULL
        CHECK (
            {date_check('purchased_on')}
            AND purchased_on >= manufactured_on
        ),
    registered_on TEXT NOT NULL
        CHECK (
            {date_check('registered_on')}
            AND registered_on >= purchased_on
        ),
    contact_email TEXT
        CHECK (
            contact_email IS NULL
            OR contact_email LIKE '%@example.com'
        ),

    CHECK (
        manufacture_year =
        CAST(substr(manufactured_on, 1, 4) AS INTEGER)
    ),

    FOREIGN KEY (model_id)
        REFERENCES television_models(model_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE warranties (
    unit_id INTEGER NOT NULL,
    coverage_type TEXT NOT NULL
        CHECK (coverage_type IN ('Manufacturer', 'Extended')),
    starts_on TEXT NOT NULL
        CHECK ({date_check('starts_on')}),
    ends_on TEXT NOT NULL
        CHECK (
            {date_check('ends_on')}
            AND ends_on > starts_on
        ),
    coverage_limit_pence INTEGER NOT NULL
        CHECK (
            typeof(coverage_limit_pence) = 'integer'
            AND coverage_limit_pence > 0
        ),

    PRIMARY KEY (unit_id, coverage_type),

    FOREIGN KEY (unit_id)
        REFERENCES registered_units(unit_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE fault_reports (
    report_id INTEGER PRIMARY KEY,
    unit_id INTEGER NOT NULL,
    reported_at TEXT NOT NULL
        CHECK ({timestamp_check('reported_at')}),
    fault_category TEXT NOT NULL
        CHECK (
            fault_category IN (
                'Picture', 'Sound', 'Power', 'Connectivity', 'Remote'
            )
        ),
    fault_severity TEXT NOT NULL
        CHECK (fault_severity IN ('Low', 'Medium', 'High')),
    report_status TEXT NOT NULL
        CHECK (report_status IN ('Open', 'Resolved')),
    description TEXT
        CHECK (
            description IS NULL
            OR length(trim(description)) > 0
        ),

    FOREIGN KEY (unit_id)
        REFERENCES registered_units(unit_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE technicians (
    technician_id INTEGER PRIMARY KEY,
    technician_name TEXT NOT NULL
        CHECK (length(trim(technician_name)) > 0),
    specialism TEXT NOT NULL
        CHECK (
            specialism IN ('Electronics', 'Display', 'Software')
        ),
    experience_years INTEGER NOT NULL
        CHECK (
            typeof(experience_years) = 'integer'
            AND experience_years BETWEEN 0 AND 45
        ),
    contact_email TEXT UNIQUE
        CHECK (
            contact_email IS NULL
            OR contact_email LIKE '%@example.com'
        )
);

CREATE TABLE repair_actions (
    report_id INTEGER NOT NULL,
    action_sequence INTEGER NOT NULL
        CHECK (
            typeof(action_sequence) = 'integer'
            AND action_sequence > 0
        ),
    technician_id INTEGER NOT NULL,
    action_type TEXT NOT NULL
        CHECK (
            action_type IN (
                'Diagnosis', 'Adjustment',
                'Component replacement', 'Software update'
            )
        ),
    started_at TEXT NOT NULL
        CHECK ({timestamp_check('started_at')}),
    completed_at TEXT NOT NULL
        CHECK (
            {timestamp_check('completed_at')}
            AND completed_at > started_at
        ),
    repair_duration_hours REAL NOT NULL
        CHECK (
            typeof(repair_duration_hours) IN ('integer', 'real')
            AND repair_duration_hours > 0
        ),
    repair_cost_pence INTEGER NOT NULL
        CHECK (
            typeof(repair_cost_pence) = 'integer'
            AND repair_cost_pence >= 0
        ),
    repair_outcome TEXT NOT NULL
        CHECK (
            repair_outcome IN ('Further work required', 'Resolved')
        ),
    notes TEXT
        CHECK (notes IS NULL OR length(trim(notes)) > 0),

    PRIMARY KEY (report_id, action_sequence),

    CHECK (
        abs(
            repair_duration_hours -
            (julianday(completed_at) - julianday(started_at)) * 24
        ) < 0.0001
    ),

    FOREIGN KEY (report_id)
        REFERENCES fault_reports(report_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,

    FOREIGN KEY (technician_id)
        REFERENCES technicians(technician_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE INDEX idx_units_model ON registered_units(model_id);
CREATE INDEX idx_fault_unit ON fault_reports(unit_id);
CREATE INDEX idx_fault_date ON fault_reports(reported_at);
CREATE INDEX idx_repair_technician ON repair_actions(technician_id);
"""

BUSINESS_RULES = """
CREATE VIEW business_rule_violations AS

SELECT 'Manufacture before model launch' AS violation
FROM registered_units u
JOIN television_models m ON m.model_id = u.model_id
WHERE u.manufacture_year < m.launch_year

UNION ALL

SELECT 'Warranty before purchase'
FROM warranties w
JOIN registered_units u ON u.unit_id = w.unit_id
WHERE w.starts_on < u.purchased_on

UNION ALL

SELECT 'Manufacturer warranty does not start at purchase'
FROM warranties w
JOIN registered_units u ON u.unit_id = w.unit_id
WHERE w.coverage_type = 'Manufacturer'
  AND w.starts_on != u.purchased_on

UNION ALL

SELECT 'Extended coverage overlaps manufacturer coverage'
FROM warranties e
JOIN warranties m ON m.unit_id = e.unit_id
WHERE e.coverage_type = 'Extended'
  AND m.coverage_type = 'Manufacturer'
  AND e.starts_on <= m.ends_on

UNION ALL

SELECT 'Fault before registration'
FROM fault_reports f
JOIN registered_units u ON u.unit_id = f.unit_id
WHERE date(f.reported_at) < u.registered_on

UNION ALL

SELECT 'Repair before fault report'
FROM repair_actions a
JOIN fault_reports f ON f.report_id = a.report_id
WHERE a.started_at < f.reported_at

UNION ALL

SELECT 'Repair actions overlap or are out of sequence'
FROM repair_actions later
JOIN repair_actions earlier
  ON earlier.report_id = later.report_id
 AND earlier.action_sequence < later.action_sequence
WHERE later.started_at < earlier.completed_at;
"""


# ============================================================
# 3. Generate fictional models
# ============================================================

brands = ["SimVision", "FictionView", "DemoScreen", "SamplePixel"]
models = []

for model_id in range(1, MODEL_COUNT + 1):
    technology = (
        ["LCD", "QLED", "OLED"][model_id - 1]
        if model_id <= 3
        else rng.choices(
            ["LCD", "QLED", "OLED"],
            weights=[50, 30, 20],
            k=1
        )[0]
    )

    models.append((
        model_id,
        f"TV-SIM-{model_id:03d}",
        rng.choice(brands),
        technology,
        float(rng.choice([24, 32, 43, 50, 55, 65, 75])),
        rng.choice([2020, 2021])
    ))


# ============================================================
# 4. Generate individual units
# ============================================================

missing_email_ids = set(
    rng.sample(range(1, UNIT_COUNT + 1), MISSING_EMAIL_COUNT)
)

model_weights = [
    rng.lognormvariate(0, 0.7)
    for _ in models
]

units = []

for unit_id in range(1, UNIT_COUNT + 1):
    model_id = (
        unit_id
        if unit_id <= MODEL_COUNT
        else rng.choices(
            range(1, MODEL_COUNT + 1),
            weights=model_weights,
            k=1
        )[0]
    )

    manufactured = datetime(2022, 1, 1) + timedelta(
        days=rng.randint(0, 600)
    )

    purchased = manufactured + timedelta(days=rng.randint(7, 100))
    registered = purchased + timedelta(days=rng.randint(0, 30))

    units.append((
        unit_id,
        model_id,
        f"SIM-SERIAL-{unit_id:07d}",
        manufactured.year,
        manufactured.date().isoformat(),
        purchased.date().isoformat(),
        registered.date().isoformat(),
        None if unit_id in missing_email_ids
        else f"registration.{unit_id:04d}@example.com"
    ))

unit_lookup = {row[0]: row for row in units}


# ============================================================
# 5. Generate warranty policies
# ============================================================

extended_unit_ids = set(
    rng.sample(range(1, UNIT_COUNT + 1), 300)
)

warranties = []

for unit in units:
    unit_id = unit[0]
    purchase_date = datetime.fromisoformat(unit[5])

    # Fictional policy: manufacturer coverage lasts 365 calendar days,
    # counting the purchase date as the first day.
    manufacturer_end = purchase_date + timedelta(days=364)

    warranties.append((
        unit_id,
        "Manufacturer",
        purchase_date.date().isoformat(),
        manufacturer_end.date().isoformat(),
        rng.choice([30000, 50000, 80000])
    ))

    if unit_id in extended_unit_ids:
        extension_start = manufacturer_end + timedelta(days=1)
        extension_end = extension_start + timedelta(days=729)

        warranties.append((
            unit_id,
            "Extended",
            extension_start.date().isoformat(),
            extension_end.date().isoformat(),
            rng.choice([30000, 50000, 80000])
        ))


# ============================================================
# 6. Generate technicians
# ============================================================

first_names = [
    "Alex", "Sam", "Jordan", "Taylor", "Morgan",
    "Casey", "Jamie", "Robin", "Avery", "Drew"
]
last_names = ["Alder", "Birch"]

technicians = []

for technician_id in range(1, TECHNICIAN_COUNT + 1):
    technicians.append((
        technician_id,
        f"{first_names[(technician_id - 1) % 10]} "
        f"{last_names[(technician_id - 1) // 10]}",
        rng.choice(["Electronics", "Display", "Software"]),
        rng.randint(1, 20),
        f"technician.{technician_id:02d}@example.com"
    ))


# ============================================================
# 7. Generate original fault reports
# ============================================================

# Only 900 units receive reports; others have no reported faults.
# Weighted selection creates repeated reports for some units.
reporting_units = rng.sample(range(1, UNIT_COUNT + 1), 900)
unit_weights = [
    rng.lognormvariate(0, 0.6)
    for _ in reporting_units
]

fault_descriptions = {
    "Picture": "Picture flickering or display distortion.",
    "Sound": "Intermittent or absent audio.",
    "Power": "Unit fails to start or switches off.",
    "Connectivity": "Network or input connection interruption.",
    "Remote": "Remote-control response unavailable."
}

reports = []

for report_id in range(1, ORIGINAL_REPORT_COUNT + 1):
    unit_id = (
        reporting_units[report_id - 1]
        if report_id <= len(reporting_units)
        else rng.choices(
            reporting_units,
            weights=unit_weights,
            k=1
        )[0]
    )

    registered = datetime.fromisoformat(unit_lookup[unit_id][6])

    reported = registered + timedelta(
        days=rng.randint(1, 700),
        hours=rng.randint(8, 17),
        minutes=rng.randint(0, 59)
    )

    # Seconds distinguish original events from deliberate duplicates.
    reported += timedelta(seconds=report_id)

    category = rng.choices(
        ["Picture", "Sound", "Power", "Connectivity", "Remote"],
        weights=[25, 20, 15, 25, 15],
        k=1
    )[0]

    if category in ("Power", "Picture"):
        severity = rng.choices(
            ["Low", "Medium", "High"],
            weights=[25, 50, 25],
            k=1
        )[0]
    else:
        severity = rng.choices(
            ["Low", "Medium", "High"],
            weights=[65, 30, 5],
            k=1
        )[0]

    reports.append((
        report_id,
        unit_id,
        iso(reported),
        category,
        severity,
        "Resolved" if report_id <= 1200 else "Open",
        fault_descriptions[category]
    ))


# ============================================================
# 8. Deliberate missing descriptions and duplicate reports
# ============================================================

# Copy only open reports to represent repeated unresolved submissions.
duplicate_sources = rng.sample(
    list(range(1200, ORIGINAL_REPORT_COUNT)),
    DUPLICATE_COUNT
)

missing_candidates = [
    index
    for index in range(ORIGINAL_REPORT_COUNT)
    if index not in set(duplicate_sources)
]

missing_description_indices = rng.sample(
    missing_candidates,
    MISSING_DESCRIPTION_COUNT
)

for index in missing_description_indices:
    row = list(reports[index])
    row[6] = None
    reports[index] = tuple(row)

# A duplicate has the same unit, timestamp, category, severity,
# status and description, but a different primary key.
for number, source_index in enumerate(duplicate_sources, start=1):
    row = list(reports[source_index])
    row[0] = ORIGINAL_REPORT_COUNT + number
    reports.append(tuple(row))


# ============================================================
# 9. Generate repair actions
# ============================================================

repairs = []

# Fictional service-cost ranges in pence.
replacement_costs = {
    "Picture": (12000, 45000),
    "Sound": (4000, 14000),
    "Power": (6000, 22000),
    "Connectivity": (2000, 9000),
    "Remote": (1000, 4000)
}

for report in reports[:1200]:
    report_id = report[0]
    category = report[3]
    reported = datetime.fromisoformat(report[2])

    # Alternate one and three actions:
    # 600 * 1 + 600 * 3 = 2,400 actions.
    action_count = 1 if report_id % 2 else 3
    next_start = reported + timedelta(
        days=rng.randint(1, 7),
        hours=rng.randint(0, 6)
    )

    for sequence in range(1, action_count + 1):
        if action_count == 1:
            action_type = (
                "Software update"
                if category == "Connectivity"
                else "Adjustment"
            )
        elif sequence == 1:
            action_type = "Diagnosis"
        elif sequence == 2:
            action_type = (
                "Software update"
                if category == "Connectivity"
                else "Component replacement"
            )
        else:
            action_type = "Adjustment"

        if action_type == "Diagnosis":
            duration_minutes = rng.randint(30, 120)
            cost = rng.randint(1500, 4500)

        elif action_type == "Component replacement":
            duration_minutes = rng.randint(90, 360)
            low, high = replacement_costs[category]
            cost = rng.randint(low, high)

        elif action_type == "Software update":
            duration_minutes = rng.randint(30, 150)
            cost = rng.randint(1000, 6000)

        else:
            duration_minutes = rng.randint(20, 90)
            cost = rng.randint(500, 3500)

        completed = next_start + timedelta(minutes=duration_minutes)

        repairs.append((
            report_id,
            sequence,
            rng.randint(1, TECHNICIAN_COUNT),
            action_type,
            iso(next_start),
            iso(completed),
            duration_minutes / 60,
            cost,
            "Resolved" if sequence == action_count
            else "Further work required",
            None if sequence == action_count
            else "Additional service action required."
        ))

        next_start = completed + timedelta(hours=rng.randint(1, 24))

# Duration means elapsed action time, not technician labour time.
# Cost means service cost, not the amount charged to the customer.
# All repairs in this dataset are completed; open reports have no actions.


# ============================================================
# 10. Create and populate SQLite
# ============================================================

connection = sqlite3.connect(DATABASE_PATH)

try:
    connection.execute("PRAGMA foreign_keys = ON")

    if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
        raise RuntimeError("Foreign-key enforcement is disabled.")

    connection.executescript(SCHEMA)
    connection.executescript(BUSINESS_RULES)

    # Check cross-table rules after child and parent changes.
    for table in (
        "television_models", "registered_units", "warranties",
        "fault_reports", "repair_actions"
    ):
        for operation in ("INSERT", "UPDATE"):
            connection.execute(f"""
                CREATE TRIGGER validate_{table}_{operation.lower()}
                AFTER {operation} ON {table}
                BEGIN
                    SELECT CASE WHEN EXISTS (
                        SELECT 1 FROM business_rule_violations
                    )
                    THEN RAISE(ABORT, 'Television business rule violated')
                    END;
                END;
            """)

    with connection:
        connection.executemany(
            "INSERT INTO television_models VALUES (?, ?, ?, ?, ?, ?)",
            models
        )
        connection.executemany(
            "INSERT INTO registered_units VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            units
        )
        connection.executemany(
            "INSERT INTO warranties VALUES (?, ?, ?, ?, ?)",
            warranties
        )
        connection.executemany(
            "INSERT INTO technicians VALUES (?, ?, ?, ?, ?)",
            technicians
        )
        connection.executemany(
            "INSERT INTO fault_reports VALUES (?, ?, ?, ?, ?, ?, ?)",
            reports
        )
        connection.executemany(
            """
            INSERT INTO repair_actions
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            repairs
        )


    # ========================================================
    # 11. Validate counts, columns and keys
    # ========================================================

    def scalar(sql, parameters=()):
        return connection.execute(sql, parameters).fetchone()[0]


    expected_counts = {
        "television_models": 40,
        "registered_units": 1200,
        "warranties": 1500,
        "fault_reports": 1818,
        "technicians": 20,
        "repair_actions": 2400
    }

    composite_keys = {}

    print("TABLE COUNTS, COLUMNS AND KEYS\n")

    for table, expected in expected_counts.items():
        actual = scalar(f"SELECT COUNT(*) FROM {table}")

        if actual != expected:
            raise RuntimeError(f"Incorrect row count: {table}")

        columns = connection.execute(
            f"PRAGMA table_info({table})"
        ).fetchall()

        primary_key = [
            column[1]
            for column in sorted(columns, key=lambda item: item[5])
            if column[5] > 0
        ]

        if not primary_key:
            raise RuntimeError(f"Missing primary key: {table}")

        if len(primary_key) > 1:
            composite_keys[table] = primary_key

            if any(
                column[5] > 0 and column[3] != 1
                for column in columns
            ):
                raise RuntimeError("Nullable composite-key component.")

        print(f"{table}: {actual:,} rows")
        print(
            "Columns:",
            ", ".join(
                f"{column[1]} ({column[2]})"
                for column in columns
            )
        )
        print("Primary key:", ", ".join(primary_key))

        for fk in connection.execute(
            f"PRAGMA foreign_key_list({table})"
        ):
            print(f"Foreign key: {fk[3]} → {fk[2]}.{fk[4]}")

        print()

    if len(composite_keys) != 2:
        raise RuntimeError("Expected two composite primary keys.")

    if len(connection.execute(
        "PRAGMA table_info(repair_actions)"
    ).fetchall()) < 7:
        raise RuntimeError("Seven-column requirement not met.")

    if scalar("SELECT COUNT(*) FROM business_rule_violations"):
        raise RuntimeError("Business-rule violations detected.")


    # ========================================================
    # 12. Validate missing and duplicate data
    # ========================================================

    missing_emails = scalar("""
        SELECT COUNT(*) FROM registered_units
        WHERE contact_email IS NULL
    """)

    missing_descriptions = scalar("""
        SELECT COUNT(*) FROM fault_reports
        WHERE description IS NULL
    """)

    missing_notes = scalar("""
        SELECT COUNT(*) FROM repair_actions
        WHERE notes IS NULL
    """)

    duplicate_groups, extra_duplicate_rows = connection.execute("""
        SELECT COUNT(*), COALESCE(SUM(copies - 1), 0)
        FROM (
            SELECT COUNT(*) AS copies
            FROM fault_reports
            GROUP BY unit_id, reported_at, fault_category,
                     fault_severity, report_status, description
            HAVING COUNT(*) > 1
        )
    """).fetchone()

    if missing_emails != MISSING_EMAIL_COUNT:
        raise RuntimeError("Missing email count mismatch.")

    if missing_descriptions != MISSING_DESCRIPTION_COUNT:
        raise RuntimeError("Missing description count mismatch.")

    if (
        duplicate_groups != DUPLICATE_COUNT
        or extra_duplicate_rows != DUPLICATE_COUNT
    ):
        raise RuntimeError("Duplicate count mismatch.")

    print("MISSING AND DUPLICATE DATA\n")

    print(
        f"Missing registration emails: {missing_emails}/1200 "
        f"({missing_emails / 1200 * 100:.2f}%)"
    )

    print(
        f"Missing descriptions: {missing_descriptions}/1800 "
        f"({missing_descriptions / 1800 * 100:.2f}% of original reports)"
    )

    print(
        f"Missing descriptions: {missing_descriptions}/1818 "
        f"({missing_descriptions / 1818 * 100:.2f}% of final reports)"
    )

    print(
        f"Optional repair notes without comments: {missing_notes}/2400 "
        f"({missing_notes / 2400 * 100:.2f}%)"
    )

    print(f"Duplicate report groups: {duplicate_groups}")

    print(
        f"Extra duplicate reports: {extra_duplicate_rows}/1818 "
        f"({extra_duplicate_rows / 1818 * 100:.2f}%)"
    )


    # ========================================================
    # 13. Validate scenario relationships
    # ========================================================

    # These describe this generated scenario, rather than all possible
    # future workflow states supported by the schema.

    if scalar("""
        SELECT COUNT(*)
        FROM registered_units u
        WHERE NOT EXISTS (
            SELECT 1 FROM warranties w
            WHERE w.unit_id = u.unit_id
              AND w.coverage_type = 'Manufacturer'
        )
    """):
        raise RuntimeError("A unit lacks manufacturer coverage.")

    if scalar("""
        SELECT COUNT(*)
        FROM fault_reports f
        WHERE f.report_status = 'Resolved'
          AND NOT EXISTS (
              SELECT 1 FROM repair_actions a
              WHERE a.report_id = f.report_id
                AND a.repair_outcome = 'Resolved'
          )
    """):
        raise RuntimeError("Resolved report lacks a resolved action.")

    if scalar("""
        SELECT COUNT(*)
        FROM repair_actions a
        JOIN fault_reports f ON f.report_id = a.report_id
        WHERE f.report_status = 'Open'
    """):
        raise RuntimeError("Unexpected actions on open reports.")

    if scalar("""
        SELECT COUNT(*)
        FROM repair_actions a
        WHERE a.action_sequence = (
            SELECT MAX(b.action_sequence)
            FROM repair_actions b
            WHERE b.report_id = a.report_id
        )
        AND a.repair_outcome != 'Resolved'
    """):
        raise RuntimeError("Final repair action is not resolved.")

    severities = {
        row[0]
        for row in connection.execute(
            "SELECT DISTINCT fault_severity FROM fault_reports"
        )
    }

    if severities != {"Low", "Medium", "High"}:
        raise RuntimeError("Ordinal categories are incomplete.")


    # ========================================================
    # 14. Invalid-operation tests — always rolled back
    # ========================================================

    def expect_rejection(name, sql, parameters=()):
        connection.execute("SAVEPOINT constraint_test")

        try:
            connection.execute(sql, parameters)

        except sqlite3.IntegrityError:
            print(f"PASS: {name}")

        else:
            raise RuntimeError(
                f"Invalid operation unexpectedly accepted: {name}"
            )

        finally:
            connection.execute("ROLLBACK TO constraint_test")
            connection.execute("RELEASE constraint_test")


    print("\nCONSTRAINT TESTS\n")

    expect_rejection(
        "Missing required model name",
        """
        INSERT INTO television_models
        VALUES (9999, NULL, 'Demo', 'LCD', 43, 2021)
        """
    )

    expect_rejection(
        "Duplicate serial number",
        """
        UPDATE registered_units
        SET serial_number = (
            SELECT serial_number FROM registered_units WHERE unit_id = 1
        )
        WHERE unit_id = 2
        """
    )

    expect_rejection(
        "Invalid foreign key",
        """
        INSERT INTO fault_reports
        VALUES (
            9999, 9999, '2025-01-01 12:00:00',
            'Sound', 'Low', 'Open', NULL
        )
        """
    )

    expect_rejection(
        "Duplicate warranty composite key",
        "INSERT INTO warranties SELECT * FROM warranties LIMIT 1"
    )

    expect_rejection(
        "Duplicate repair composite key",
        "INSERT INTO repair_actions SELECT * FROM repair_actions LIMIT 1"
    )

    expect_rejection(
        "Invalid severity",
        "UPDATE fault_reports SET fault_severity='Critical' WHERE report_id=1"
    )

    expect_rejection(
        "Negative repair cost",
        "UPDATE repair_actions SET repair_cost_pence=-1 WHERE report_id=1"
    )

    expect_rejection(
        "Duration inconsistent with timestamps",
        """
        UPDATE repair_actions
        SET repair_duration_hours=999
        WHERE report_id=1
        """
    )

    expect_rejection(
        "Invalid calendar date",
        """
        UPDATE registered_units
        SET manufactured_on='2022-02-30'
        WHERE unit_id=1
        """
    )

    expect_rejection(
        "Warranty ends before it starts",
        """
        UPDATE warranties
        SET ends_on='2000-01-01'
        WHERE unit_id=1
        """
    )

    expect_rejection(
        "Fault before registration",
        """
        UPDATE fault_reports
        SET reported_at='2000-01-01 12:00:00'
        WHERE report_id=1
        """
    )

    expect_rejection(
        "Model launched after unit manufacture",
        """
        UPDATE television_models
        SET launch_year=2030
        WHERE model_id=1
        """
    )

    expect_rejection(
        "Manufacture year inconsistent with date",
        """
        UPDATE registered_units
        SET manufacture_year=2000
        WHERE unit_id=1
        """
    )


    # ========================================================
    # 15. Integrity and retrieval checks
    # ========================================================

    integrity = [
        row[0]
        for row in connection.execute("PRAGMA integrity_check")
    ]

    foreign_key_errors = connection.execute(
        "PRAGMA foreign_key_check"
    ).fetchall()

    if integrity != ["ok"] or foreign_key_errors:
        raise RuntimeError("Database integrity validation failed.")

    for table, expected in expected_counts.items():
        if scalar(f"SELECT COUNT(*) FROM {table}") != expected:
            raise RuntimeError("Constraint tests changed the row counts.")

    print("\nFINAL VALIDATION\n")
    print("Integrity check: ok")
    print("Foreign-key violations: 0")
    print("Business-rule violations: 0")
    print("Composite primary keys: 2")
    print("Repair table: 10 columns and 2,400 rows")
    print("All four measurement types represented")
    print("All 13 invalid-operation tests rejected")
    print("Missing and duplicate records retained")

    print("\nFAULT SEVERITY COUNTS\n")

    for severity, count in connection.execute("""
        SELECT fault_severity, COUNT(*)
        FROM fault_reports
        GROUP BY fault_severity
        ORDER BY CASE fault_severity
            WHEN 'Low' THEN 1
            WHEN 'Medium' THEN 2
            ELSE 3
        END
    """):
        print(f"{severity}: {count:,}")

    print("\nSERVICE COST AND DURATION BY FAULT CATEGORY\n")

    for category, actions, cost, hours in connection.execute("""
        SELECT f.fault_category,
               COUNT(*),
               ROUND(AVG(a.repair_cost_pence) / 100.0, 2),
               ROUND(AVG(a.repair_duration_hours), 2)
        FROM repair_actions a
        JOIN fault_reports f ON f.report_id = a.report_id
        GROUP BY f.fault_category
        ORDER BY f.fault_category
    """):
        print(
            f"{category}: {actions} actions, "
            f"mean cost £{cost:.2f}, mean duration {hours:.2f} hours"
        )

    print("\nREPORTS WITH DATE-ELIGIBLE WARRANTY COVERAGE\n")

    # This establishes date eligibility only.
    # It does not adjudicate exclusions, remaining limits,
    # prior claims or the customer's final payment.
    date_eligible_reports = scalar("""
        WITH distinct_reports AS (
            SELECT DISTINCT unit_id, reported_at, fault_category,
                            fault_severity, report_status, description
            FROM fault_reports
        )
        SELECT COUNT(*)
        FROM distinct_reports f
        WHERE EXISTS (
            SELECT 1 FROM warranties w
            WHERE w.unit_id = f.unit_id
              AND date(f.reported_at) BETWEEN w.starts_on AND w.ends_on
        )
    """)

    print(
        f"{date_eligible_reports:,} distinct fault events "
        "fall within a policy date range."
    )

    connection.commit()

finally:
    connection.close()


# ============================================================
# 16. Reopen saved database and download only the DB file
# ============================================================

with sqlite3.connect(DATABASE_PATH) as saved:
    saved.execute("PRAGMA foreign_keys = ON")

    if saved.execute(
        "PRAGMA integrity_check"
    ).fetchone()[0] != "ok":
        raise RuntimeError("Saved database integrity check failed.")

    if saved.execute(
        "SELECT COUNT(*) FROM fault_reports"
    ).fetchone()[0] != 1818:
        raise RuntimeError("Saved database row count mismatch.")

    if saved.execute("PRAGMA foreign_key_check").fetchall():
        raise RuntimeError("Saved database has foreign-key violations.")

print("\nDatabase saved and reopened successfully.")
print("Downloading television_warranty.db ...")

files.download(str(DATABASE_PATH))