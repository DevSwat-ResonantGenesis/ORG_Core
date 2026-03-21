#!/bin/bash
# Initialize PostgreSQL replica from primary

set -e

# Wait for primary to be ready
until pg_isready -h auth_db_primary -p 5432 -U replicator; do
    echo "Waiting for primary..."
    sleep 2
done

# Check if data directory is empty
if [ -z "$(ls -A /var/lib/postgresql/data 2>/dev/null)" ]; then
    echo "Initializing replica from primary..."
    
    # Create base backup from primary
    PGPASSWORD=$PGPASSWORD pg_basebackup \
        -h auth_db_primary \
        -p 5432 \
        -U replicator \
        -D /var/lib/postgresql/data \
        -Fp \
        -Xs \
        -P \
        -R
    
    # Configure recovery
    cat >> /var/lib/postgresql/data/postgresql.auto.conf <<EOF
primary_conninfo = 'host=auth_db_primary port=5432 user=replicator password=${PGPASSWORD}'
primary_slot_name = 'replica_slot'
EOF

    # Create standby signal
    touch /var/lib/postgresql/data/standby.signal
    
    echo "Replica initialized successfully"
else
    echo "Data directory not empty, assuming already initialized"
fi

# Start PostgreSQL
exec postgres "$@"
