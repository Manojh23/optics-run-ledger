from alembic import op

revision = "0002_measurements"
down_revision = "0001_lineage"


def upgrade():
    op.execute("""
    CREATE TABLE imports (
        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        instrument varchar(64) NOT NULL,
        external_id varchar(64) NOT NULL,
        sha256 char(64) NOT NULL,
        received_at timestamptz NOT NULL DEFAULT now(),
        UNIQUE (instrument, external_id)
    );
    CREATE TABLE measurements (
        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        import_id bigint NOT NULL REFERENCES imports (id),
        serial varchar(64) NOT NULL REFERENCES devices (serial),
        measured_at timestamptz NOT NULL,
        value_nm double precision NOT NULL CHECK (value_nm >= 0 AND value_nm <= 1000000),
        spec_max_nm double precision NOT NULL CHECK (spec_max_nm > 0 AND spec_max_nm <= 1000000),
        passed boolean GENERATED ALWAYS AS (value_nm <= spec_max_nm) STORED,
        UNIQUE (import_id, serial, measured_at)
    );
    CREATE INDEX device_measurement_order_idx ON measurements (serial, measured_at DESC, id DESC);
    CREATE VIEW device_quality AS
      SELECT d.serial, d.run_code, r.design_revision, r.recipe_revision, r.printer,
             r.printed_at, r.substrate_code, s.material_lot,
             m.measured_at, m.value_nm, m.spec_max_nm, i.instrument,
             CASE WHEN m.id IS NULL THEN 'unmeasured'
                  WHEN m.passed THEN 'pass' ELSE 'fail' END AS status
        FROM devices d
        JOIN print_runs r ON r.code=d.run_code
        JOIN substrates s ON s.code=r.substrate_code
        LEFT JOIN LATERAL (
            SELECT * FROM measurements WHERE serial=d.serial
            ORDER BY measured_at DESC, id DESC LIMIT 1
        ) m ON true
        LEFT JOIN imports i ON i.id=m.import_id;
    """)


def downgrade():
    op.execute("DROP VIEW device_quality; DROP TABLE measurements; DROP TABLE imports;")
