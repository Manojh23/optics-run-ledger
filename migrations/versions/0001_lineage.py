from alembic import op

revision = "0001_lineage"
down_revision = None


def upgrade():
    op.execute("""
    CREATE TABLE substrates (
        code varchar(64) PRIMARY KEY,
        material_lot varchar(64) NOT NULL,
        material varchar(80) NOT NULL
    );
    CREATE INDEX substrate_lot_idx ON substrates (material_lot, code);
    CREATE TABLE print_runs (
        code varchar(64) PRIMARY KEY,
        substrate_code varchar(64) NOT NULL REFERENCES substrates (code),
        design_revision varchar(64) NOT NULL,
        recipe_revision varchar(64) NOT NULL,
        printer varchar(64) NOT NULL,
        printed_at timestamptz NOT NULL
    );
    CREATE INDEX run_substrate_idx ON print_runs (substrate_code);
    CREATE TABLE devices (
        serial varchar(64) PRIMARY KEY,
        run_code varchar(64) NOT NULL REFERENCES print_runs (code),
        position varchar(64) NOT NULL,
        UNIQUE (run_code, position)
    );
    """)


def downgrade():
    op.execute("DROP TABLE devices; DROP TABLE print_runs; DROP TABLE substrates;")
