"""Benchmarking Script for ResonantGenesis Backend.

Performs detailed benchmarking of individual API endpoints to measure
baseline performance, compare endpoints, and track performance over time.

Author: Agent 7 - ResonantGenesis Team
Created: February 21, 2026

Usage:
    python benchmark.py --url https://api.resonantgenesis.xyz --iterations 100
"""

import asyncio
import aiohttp
import argparse
import time
import json
import statistics
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime


@dataclass
class EndpointBenchmark:
    """Benchmark results for a single endpoint."""
    endpoint: str
    method: str
    iterations: int
    latencies: List[float] = field(default_factory=list)
    successes: int = 0
    failures: int = 0
    
    @property
    def mean_latency(self) -> float:
        return statistics.mean(self.latencies) if self.latencies else 0
    
    @property
    def median_latency(self) -> float:
        return statistics.median(self.latencies) if self.latencies else 0
    
    @property
    def std_dev(self) -> float:
        return statistics.stdev(self.latencies) if len(self.latencies) > 1 else 0
    
    @property
    def min_latency(self) -> float:
        return min(self.latencies) if self.latencies else 0
    
    @property
    def max_latency(self) -> float:
        return max(self.latencies) if self.latencies else 0
    
    def percentile(self, p: float) -> float:
        if not self.latencies:
            return 0
        sorted_latencies = sorted(self.latencies)
        index = int(len(sorted_latencies) * p / 100)
        return sorted_latencies[min(index, len(sorted_latencies) - 1)]
    
    @property
    def success_rate(self) -> float:
        total = self.successes + self.failures
        return self.successes / total * 100 if total > 0 else 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "endpoint": self.endpoint,
            "method": self.method,
            "iterations": self.iterations,
            "success_rate": round(self.success_rate, 2),
            "latency": {
                "mean_ms": round(self.mean_latency, 3),
                "median_ms": round(self.median_latency, 3),
                "std_dev_ms": round(self.std_dev, 3),
                "min_ms": round(self.min_latency, 3),
                "max_ms": round(self.max_latency, 3),
                "p50_ms": round(self.percentile(50), 3),
                "p90_ms": round(self.percentile(90), 3),
                "p95_ms": round(self.percentile(95), 3),
                "p99_ms": round(self.percentile(99), 3),
            }
        }


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark."""
    base_url: str
    iterations: int = 100
    warmup_iterations: int = 10
    concurrency: int = 1
    auth_token: Optional[str] = None
    endpoints: List[Dict[str, Any]] = field(default_factory=list)


# Default endpoints to benchmark
DEFAULT_ENDPOINTS = [
    {"method": "GET", "path": "/health", "name": "Health Check"},
    {"method": "GET", "path": "/", "name": "Root"},
    {"method": "GET", "path": "/api/v1/status", "name": "API Status"},
]


class Benchmarker:
    """Benchmarking engine."""
    
    def __init__(self, config: BenchmarkConfig):
        self.config = config
        self.results: List[EndpointBenchmark] = []
        self.endpoints = config.endpoints or DEFAULT_ENDPOINTS
    
    async def _make_request(
        self, 
        session: aiohttp.ClientSession, 
        endpoint: Dict[str, Any]
    ) -> tuple[float, bool]:
        """Make a single request and return latency and success."""
        method = endpoint.get("method", "GET")
        path = endpoint.get("path", "/health")
        url = f"{self.config.base_url}{path}"
        
        headers = {}
        if endpoint.get("auth") and self.config.auth_token:
            headers["Authorization"] = f"Bearer {self.config.auth_token}"
        
        body = endpoint.get("body")
        
        start_time = time.perf_counter()
        try:
            async with session.request(
                method, 
                url, 
                headers=headers,
                json=body,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                latency_ms = (time.perf_counter() - start_time) * 1000
                await response.read()
                success = 200 <= response.status < 400
                return latency_ms, success
        except Exception:
            latency_ms = (time.perf_counter() - start_time) * 1000
            return latency_ms, False
    
    async def _benchmark_endpoint(
        self, 
        session: aiohttp.ClientSession, 
        endpoint: Dict[str, Any]
    ) -> EndpointBenchmark:
        """Benchmark a single endpoint."""
        name = endpoint.get("name", endpoint.get("path", "Unknown"))
        method = endpoint.get("method", "GET")
        path = endpoint.get("path", "/")
        
        print(f"  Benchmarking: {method} {path} ({name})")
        
        benchmark = EndpointBenchmark(
            endpoint=path,
            method=method,
            iterations=self.config.iterations
        )
        
        # Warmup
        print(f"    Warming up ({self.config.warmup_iterations} iterations)...")
        for _ in range(self.config.warmup_iterations):
            await self._make_request(session, endpoint)
        
        # Actual benchmark
        print(f"    Running benchmark ({self.config.iterations} iterations)...")
        for i in range(self.config.iterations):
            latency, success = await self._make_request(session, endpoint)
            benchmark.latencies.append(latency)
            if success:
                benchmark.successes += 1
            else:
                benchmark.failures += 1
            
            # Progress indicator
            if (i + 1) % 25 == 0:
                print(f"      Progress: {i + 1}/{self.config.iterations}")
        
        print(f"    Done: {benchmark.mean_latency:.2f}ms mean, {benchmark.success_rate:.1f}% success")
        
        return benchmark
    
    async def run(self) -> List[EndpointBenchmark]:
        """Run benchmarks for all endpoints."""
        print("=" * 60)
        print("BENCHMARK")
        print("=" * 60)
        print(f"URL: {self.config.base_url}")
        print(f"Iterations: {self.config.iterations}")
        print(f"Warmup: {self.config.warmup_iterations}")
        print(f"Endpoints: {len(self.endpoints)}")
        print("=" * 60)
        print()
        
        self.results = []
        
        connector = aiohttp.TCPConnector(limit=10)
        async with aiohttp.ClientSession(connector=connector) as session:
            for endpoint in self.endpoints:
                benchmark = await self._benchmark_endpoint(session, endpoint)
                self.results.append(benchmark)
                print()
        
        return self.results
    
    def print_results(self):
        """Print benchmark results."""
        print("\n" + "=" * 80)
        print("BENCHMARK RESULTS")
        print("=" * 80)
        
        # Header
        print(f"{'Endpoint':<30} {'Mean':>10} {'Median':>10} {'P95':>10} {'P99':>10} {'Success':>10}")
        print("-" * 80)
        
        # Results
        for result in self.results:
            print(f"{result.endpoint:<30} "
                  f"{result.mean_latency:>9.2f}ms "
                  f"{result.median_latency:>9.2f}ms "
                  f"{result.percentile(95):>9.2f}ms "
                  f"{result.percentile(99):>9.2f}ms "
                  f"{result.success_rate:>9.1f}%")
        
        print("=" * 80)
        
        # Find fastest and slowest
        if self.results:
            sorted_by_mean = sorted(self.results, key=lambda x: x.mean_latency)
            print(f"\nFastest: {sorted_by_mean[0].endpoint} ({sorted_by_mean[0].mean_latency:.2f}ms)")
            print(f"Slowest: {sorted_by_mean[-1].endpoint} ({sorted_by_mean[-1].mean_latency:.2f}ms)")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert results to dictionary."""
        return {
            "timestamp": datetime.now().isoformat(),
            "config": {
                "base_url": self.config.base_url,
                "iterations": self.config.iterations,
                "warmup_iterations": self.config.warmup_iterations,
            },
            "results": [r.to_dict() for r in self.results]
        }


def main():
    parser = argparse.ArgumentParser(description="Benchmark ResonantGenesis backend")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL")
    parser.add_argument("--iterations", type=int, default=100, help="Iterations per endpoint")
    parser.add_argument("--warmup", type=int, default=10, help="Warmup iterations")
    parser.add_argument("--token", help="Auth token")
    parser.add_argument("--output", help="Output file for JSON results")
    parser.add_argument("--endpoints", help="JSON file with custom endpoints")
    
    args = parser.parse_args()
    
    endpoints = None
    if args.endpoints:
        with open(args.endpoints) as f:
            endpoints = json.load(f)
    
    config = BenchmarkConfig(
        base_url=args.url,
        iterations=args.iterations,
        warmup_iterations=args.warmup,
        auth_token=args.token,
        endpoints=endpoints or []
    )
    
    benchmarker = Benchmarker(config)
    asyncio.run(benchmarker.run())
    benchmarker.print_results()
    
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(benchmarker.to_dict(), f, indent=2)
        print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
