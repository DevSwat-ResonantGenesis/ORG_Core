#!/bin/bash

# ===========================================
# START AUTONOMOUS AGENTS + DISTRIBUTED BLOCKCHAIN
# ===========================================

set -e

echo "=============================================="
echo "  RESONANT GENESIS - AUTONOMOUS MODE"
echo "=============================================="
echo ""
echo "This starts:"
echo "  1. Autonomous Agent Daemon (self-triggering agents)"
echo "  2. Distributed Blockchain (3-node Raft consensus)"
echo "  3. P2P Network for node communication"
echo ""

# Check for required env vars
if [ -z "$OPENAI_API_KEY" ] && [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "WARNING: No LLM API key set. Agents will not be able to think."
    echo "Set OPENAI_API_KEY or ANTHROPIC_API_KEY"
    echo ""
fi

# Start everything
echo "Starting services..."
docker-compose -f docker-compose.autonomous.yml up -d

echo ""
echo "Waiting for services to be ready..."
sleep 10

# Check status
echo ""
echo "=============================================="
echo "  SERVICE STATUS"
echo "=============================================="

# Check autonomous daemon
echo -n "Autonomous Daemon: "
if docker-compose -f docker-compose.autonomous.yml ps autonomous_daemon | grep -q "Up"; then
    echo "✅ RUNNING"
else
    echo "❌ NOT RUNNING"
fi

# Check blockchain nodes
for i in 1 2 3; do
    echo -n "Blockchain Node $i: "
    if docker-compose -f docker-compose.autonomous.yml ps blockchain_node_$i | grep -q "Up"; then
        echo "✅ RUNNING"
    else
        echo "❌ NOT RUNNING"
    fi
done

echo ""
echo "=============================================="
echo "  ENDPOINTS"
echo "=============================================="
echo ""
echo "LLM Service:        http://localhost:8010"
echo "Blockchain Node 1:  http://localhost:8601 (Leader)"
echo "Blockchain Node 2:  http://localhost:8602"
echo "Blockchain Node 3:  http://localhost:8603"
echo ""
echo "P2P Ports: 8600, 8610, 8620"
echo ""
echo "=============================================="
echo "  USAGE"
echo "=============================================="
echo ""
echo "Register an autonomous agent:"
echo '  curl -X POST http://localhost:8601/autonomous/agents/register \'
echo '    -H "Content-Type: application/json" \'
echo '    -d '"'"'{"agent_id": "agent-1", "initial_goal": "Monitor system and report anomalies"}'"'"
echo ""
echo "Check daemon status:"
echo "  curl http://localhost:8601/autonomous/daemon/status"
echo ""
echo "Check blockchain status:"
echo "  curl http://localhost:8601/distributed/status"
echo ""
echo "Submit transaction to blockchain:"
echo '  curl -X POST http://localhost:8601/distributed/transactions \'
echo '    -H "Content-Type: application/json" \'
echo '    -d '"'"'{"tx_type": "set", "payload": {"key": "test", "value": "hello"}}'"'"
echo ""
echo "=============================================="
echo "  LOGS"
echo "=============================================="
echo ""
echo "View daemon logs:     docker-compose -f docker-compose.autonomous.yml logs -f autonomous_daemon"
echo "View blockchain logs: docker-compose -f docker-compose.autonomous.yml logs -f blockchain_node_1"
echo ""
echo "To stop: docker-compose -f docker-compose.autonomous.yml down"
echo ""
