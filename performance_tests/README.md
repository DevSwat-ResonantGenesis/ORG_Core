# ResonantGenesis Performance Testing Suite

Performance testing tools for the ResonantGenesis backend services.

**Author:** Agent 7 - ResonantGenesis Team  
**Created:** February 21, 2026

---

## Overview

This directory contains three performance testing tools:

| Tool | Purpose | Use Case |
|------|---------|----------|
| `load_test.py` | Load testing | Measure throughput under sustained load |
| `stress_test.py` | Stress testing | Find breaking point and max capacity |
| `benchmark.py` | Benchmarking | Measure individual endpoint performance |

---

## Installation

```bash
pip install aiohttp
```

---

## Load Testing

Simulates sustained load with configurable concurrency to measure throughput, latency, and error rates.

### Usage

```bash
# Basic load test (60 seconds, 10 concurrent users)
python load_test.py --url https://api.resonantgenesis.xyz

# Custom configuration
python load_test.py \
    --url https://api.resonantgenesis.xyz \
    --duration 120 \
    --concurrency 50 \
    --ramp-up 10 \
    --token YOUR_AUTH_TOKEN \
    --output results.json
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--url` | localhost:8000 | Base URL to test |
| `--duration` | 60 | Test duration in seconds |
| `--concurrency` | 10 | Number of concurrent users |
| `--ramp-up` | 5 | Ramp-up time in seconds |
| `--token` | None | Auth token for protected endpoints |
| `--output` | None | JSON file for results |

### Output Metrics

- Total requests
- Success/failure counts
- Requests per second
- Latency statistics (mean, median, min, max, percentiles)
- Status code distribution
- Error breakdown

---

## Stress Testing

Gradually increases load to find the system's breaking point and maximum capacity.

### Usage

```bash
# Basic stress test
python stress_test.py --url https://api.resonantgenesis.xyz

# Custom configuration
python stress_test.py \
    --url https://api.resonantgenesis.xyz \
    --initial-users 5 \
    --max-users 200 \
    --step 20 \
    --phase-duration 30 \
    --error-threshold 0.05 \
    --output stress_results.json
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--url` | localhost:8000 | Base URL to test |
| `--initial-users` | 5 | Starting concurrent users |
| `--max-users` | 100 | Maximum concurrent users |
| `--step` | 10 | User increment per phase |
| `--phase-duration` | 30 | Duration per phase in seconds |
| `--error-threshold` | 0.1 | Error rate to trigger breaking point (0-1) |
| `--latency-threshold` | 5000 | P95 latency threshold in ms |
| `--output` | None | JSON file for results |

### Output Metrics

- Phase-by-phase results
- Breaking point (if reached)
- Maximum throughput achieved
- Optimal concurrency level

---

## Benchmarking

Measures detailed performance of individual endpoints with statistical analysis.

### Usage

```bash
# Basic benchmark
python benchmark.py --url https://api.resonantgenesis.xyz

# Custom configuration
python benchmark.py \
    --url https://api.resonantgenesis.xyz \
    --iterations 200 \
    --warmup 20 \
    --token YOUR_AUTH_TOKEN \
    --endpoints custom_endpoints.json \
    --output benchmark_results.json
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--url` | localhost:8000 | Base URL to test |
| `--iterations` | 100 | Iterations per endpoint |
| `--warmup` | 10 | Warmup iterations |
| `--token` | None | Auth token |
| `--endpoints` | None | JSON file with custom endpoints |
| `--output` | None | JSON file for results |

### Custom Endpoints File

```json
[
    {"method": "GET", "path": "/health", "name": "Health Check"},
    {"method": "GET", "path": "/api/v1/status", "name": "API Status"},
    {"method": "POST", "path": "/api/v1/identity/register", "name": "Register", "auth": true, "body": {"user_hash": "test"}}
]
```

### Output Metrics

- Per-endpoint statistics
- Mean, median, min, max latency
- Standard deviation
- Percentiles (P50, P90, P95, P99)
- Success rate
- Fastest/slowest endpoint comparison

---

## CI/CD Integration

### GitHub Actions Example

```yaml
- name: Run Performance Tests
  run: |
    pip install aiohttp
    cd performance_tests
    python benchmark.py --url ${{ secrets.API_URL }} --iterations 50 --output benchmark.json
    
- name: Upload Results
  uses: actions/upload-artifact@v4
  with:
    name: performance-results
    path: performance_tests/benchmark.json
```

---

## Interpreting Results

### Load Test

- **Good**: >95% success rate, <500ms mean latency
- **Warning**: 90-95% success rate, 500-1000ms latency
- **Critical**: <90% success rate, >1000ms latency

### Stress Test

- **Breaking Point**: Concurrency level where errors exceed threshold
- **Optimal Concurrency**: Level with highest throughput before degradation

### Benchmark

- **Baseline**: Use for regression testing
- **Compare**: Track changes over time
- **Identify**: Find slow endpoints for optimization

---

## Best Practices

1. **Run from similar network location** to production
2. **Use realistic data** in request payloads
3. **Test during off-peak hours** to avoid affecting users
4. **Establish baselines** before making changes
5. **Monitor server resources** during tests
6. **Run multiple times** for consistent results

---

## Troubleshooting

### Connection Errors

- Check URL is correct
- Verify network connectivity
- Check firewall rules

### High Error Rates

- Reduce concurrency
- Check server logs
- Verify auth token is valid

### Inconsistent Results

- Increase iterations
- Check for background processes
- Test during stable periods
