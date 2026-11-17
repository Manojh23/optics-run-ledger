CREATE ROLE ledger_dashboard LOGIN PASSWORD 'ledger-dashboard-local';
GRANT CONNECT ON DATABASE ledger TO ledger_dashboard;
GRANT USAGE ON SCHEMA public TO ledger_dashboard;
-- Grants only SELECT for tables/views created by the migration user.
ALTER DEFAULT PRIVILEGES FOR USER ledger IN SCHEMA public
  GRANT SELECT ON TABLES TO ledger_dashboard;
