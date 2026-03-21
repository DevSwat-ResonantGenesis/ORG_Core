#!/bin/bash
# Initialize PostgreSQL primary for replication

set -e

# Create replication user
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE USER replicator WITH REPLICATION ENCRYPTED PASSWORD '${POSTGRES_REPLICATION_PASSWORD:-repl_pass}';
    SELECT * FROM pg_create_physical_replication_slot('replica_slot');
EOSQL

# Update pg_hba.conf for replication
cat >> "$PGDATA/pg_hba.conf" <<EOF
# Replication connections
host replication replicator 0.0.0.0/0 md5
EOF

echo "Primary initialization complete"
