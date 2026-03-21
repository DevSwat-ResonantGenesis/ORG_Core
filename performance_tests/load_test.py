"""Load Testing Script for ResonantGenesis Backend.

Performs load testing on backend API endpoints using concurrent requests
to measure throughput, latency, and error rates under load.

Author: Agent 7 - ResonantGenesis Team
Created: February 21, 2026

Usage:
    python load_test.py --url https://api.resonantgenesis.xyz --duration 60 --concurrency 10
"""

import asyncio
import aiohttp
import argparse
import time
import statistics
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
import json


@dataclass
class RequestResult:
    """Result of a single request."""
    endpoint: str
    method: str
    status_code: int
    latency_ms: float
    success: bool
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class LoadTestConfig:
    """Configuration for load test."""
    base_url: str
    duration_seconds: int = 60
    concurrency: int = 10
    ramp_up_seconds: int = 5
    endpoints: List[Dict[str, Any]] = field(default_factory=list)
    auth_token: Optional[str] = None


@dataclass
class LoadTestResults:
    """Aggregated results from load test."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_latency_ms: float = 0
    latencies: List[float] = field(default_factory=list)
    errors: Dict[str, int] = field(default_factory=dict)
    status_codes: Dict[int, int] = field(default_factory=dict)
    requests_per_second: float = 0
    start_time: float = 0
    end_time: float = 0
    
    def add_result(self, result: RequestResult):
        """Add a request result to the aggregation."""
        self.total_requests += 1
        self.latencies.append(result.latency_ms)
        self.total_latency_ms += result.latency_ms
        
        if result.success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1
            if result.error:
                self.errors[result.error] = self.errors.get(result.error, 0) + 1
        
        self.status_codes[result.status_code] = self.status_codes.get(result.status_code, 0) + 1
    
    def calculate_stats(self):
        """Calculate final statistics."""
        duration = self.end_time - self.start_time
        if duration > 0:
            self.requests_per_second = self.total_requests / duration
    
    def get_percentile(self, p: float) -> float:
        """Get latency percentile."""
        if not self.latencies:
            return 0
        sorted_latencies = sorted(self.latencies)
        index = int(len(sorted_latencies) * p / 100)
        return sorted_latencies[min(index, len(sorted_latencies) - 1)]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert results to dictionary."""
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": self.successful_requests / max(self.total_requests, 1) * 100,
            "requests_per_second": round(self.requests_per_second, 2),
            "latency": {
                "mean_ms": round(statistics.mean(self.latencies), 2) if self.latencies else 0,
                "median_ms": round(statistics.median(self.latencies), 2) if self.latencies else 0,
                "min_ms": round(min(self.latencies), 2) if self.latencies else 0,
                "max_ms": round(max(self.latencies), 2) if self.latencies else 0,
                "p50_ms": round(self.get_percentile(50), 2),
                "p90_ms": round(self.get_percentile(90), 2),
                "p95_ms": round(self.get_percentile(95), 2),
                "p99_ms": round(self.get_percentile(99), 2),
            },
            "status_codes": self.status_codes,
            "errors": self.errors,
            "duration_seconds": round(self.end_time - self.start_time, 2),
        }


# Default endpoints to test
DEFAULT_ENDPOINTS = [
    {"method": "GET", "path": "/health", "weight": 20},
    {"method": "GET", "path": "/api/v1/status", "weight": 15},
    {"method": "GET", "path": "/api/v1/lifecycle/agents", "weight": 10, "auth": True},
    {"method": "POST", "path": "/api/v1/identity/lookup/test-hash", "weight": 5, "auth": True},
    {"method": "GET", "path": "/api/v1/blocks/latest", "weight": 10},
    {"method": "GET", "path": "/api/v1/contracts/stats", "weight": 5, "auth": True},
]


class LoadTester:
    """Load testing engine."""
    
    def __init__(self, config: LoadTestConfig):
        self.config = config
        self.results = LoadTestResults()
        self.running = False
        self.endpoints = config.endpoints or DEFAULT_ENDPOINTS
    
    def _select_endpoint(self) -> Dict[str, Any]:
        """Select an endpoint based on weights."""
        import random
        total_weight = sum(e.get("weight", 1) for e in self.endpoints)
        r = random.uniform(0, total_weight)
        cumulative = 0
        for endpoint in self.endpoints:
            cumulative += endpoint.get("weight", 1)
            if r <= cumulative:
                return endpoint
        return self.endpoints[-1]
    
    async def _make_request(
        self, 
        session: aiohttp.ClientSession, 
        endpoint: Dict[str, Any]
    ) -> RequestResult:
        """Make a single HTTP request."""
        method = endpoint.get("method", "GET")
        path = endpoint.get("path", "/health")
        url = f"{self.config.base_url}{path}"
        
        headers = {}
        if endpoint.get("auth") and self.config.auth_token:
            headers["Authorization"] = f"Bearer {self.config.auth_token}"
        
        body = endpoint.get("body")
        
        start_time = time.time()
        try:
            async with session.request(
                method, 
                url, 
                headers=headers,
                json=body,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                latency_ms = (time.time() - start_time) * 1000
                await response.read()
                
                return RequestResult(
                    endpoint=path,
                    method=method,
                    status_code=response.status,
                    latency_ms=latency_ms,
                    success=200 <= response.status < 400
                )
        except asyncio.TimeoutError:
            return RequestResult(
                endpoint=path,
                method=method,
                status_code=0,
                latency_ms=(time.time() - start_time) * 1000,
                success=False,
                error="timeout"
            )
        except Exception as e:
            return RequestResult(
                endpoint=path,
                method=method,
                status_code=0,
                latency_ms=(time.time() - start_time) * 1000,
                success=False,
                error=str(type(e).__name__)
            )
    
    async def _worker(self, session: aiohttp.ClientSession, worker_id: int):
        """Worker coroutine that makes requests."""
        # Ramp up delay
        ramp_delay = (worker_id / self.config.concurrency) * self.config.ramp_up_seconds
        await asyncio.sleep(ramp_delay)
        
        while self.running:
            endpoint = self._select_endpoint()
            result = await self._make_request(session, endpoint)
            self.results.add_result(result)
            
            # Small delay between requests
            await asyncio.sleep(0.01)
    
    async def run(self) -> LoadTestResults:
        """Run the load test."""
        print(f"Starting load test...")
        print(f"  URL: {self.config.base_url}")
        print(f"  Duration: {self.config.duration_seconds}s")
        print(f"  Concurrency: {self.config.concurrency}")
        print(f"  Ramp-up: {self.config.ramp_up_seconds}s")
        print()
        
        self.results = LoadTestResults()
        self.results.start_time = time.time()
        self.running = True
        
        connector = aiohttp.TCPConnector(limit=self.config.concurrency * 2)
        async with aiohttp.ClientSession(connector=connector) as session:
            # Start workers
            workers = [
                asyncio.create_task(self._worker(session, i))
                for i in range(self.config.concurrency)
            ]
            
            # Run for specified duration
            await asyncio.sleep(self.config.duration_seconds)
            
            # Stop workers
            self.running = False
            await asyncio.gather(*workers, return_exceptions=True)
        
        self.results.end_time = time.time()
        self.results.calculate_stats()
        
        return self.results
    
    def print_results(self):
        """Print results to console."""
        results = self.results.to_dict()
        
        print("\n" + "=" * 60)
        print("LOAD TEST RESULTS")
        print("=" * 60)
        print(f"\nTotal Requests:     {results['total_requests']}")
        print(f"Successful:         {results['successful_requests']}")
        print(f"Failed:             {results['failed_requests']}")
        print(f"Success Rate:       {results['success_rate']:.2f}%")
        print(f"Requests/Second:    {results['requests_per_second']:.2f}")
        print(f"Duration:           {results['duration_seconds']:.2f}s")
        
        print("\nLatency Statistics:")
        latency = results['latency']
        print(f"  Mean:    {latency['mean_ms']:.2f}ms")
        print(f"  Median:  {latency['median_ms']:.2f}ms")
        print(f"  Min:     {latency['min_ms']:.2f}ms")
        print(f"  Max:     {latency['max_ms']:.2f}ms")
        print(f"  P50:     {latency['p50_ms']:.2f}ms")
        print(f"  P90:     {latency['p90_ms']:.2f}ms")
        print(f"  P95:     {latency['p95_ms']:.2f}ms")
        print(f"  P99:     {latency['p99_ms']:.2f}ms")
        
        print("\nStatus Codes:")
        for code, count in sorted(results['status_codes'].items()):
            print(f"  {code}: {count}")
        
        if results['errors']:
            print("\nErrors:")
            for error, count in results['errors'].items():
                print(f"  {error}: {count}")
        
        print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Load test ResonantGenesis backend")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL")
    parser.add_argument("--duration", type=int, default=60, help="Test duration in seconds")
    parser.add_argument("--concurrency", type=int, default=10, help="Number of concurrent users")
    parser.add_argument("--ramp-up", type=int, default=5, help="Ramp-up time in seconds")
    parser.add_argument("--token", help="Auth token for authenticated endpoints")
    parser.add_argument("--output", help="Output file for JSON results")
    
    args = parser.parse_args()
    
    config = LoadTestConfig(
        base_url=args.url,
        duration_seconds=args.duration,
        concurrency=args.concurrency,
        ramp_up_seconds=args.ramp_up,
        auth_token=args.token
    )
    
    tester = LoadTester(config)
    asyncio.run(tester.run())
    tester.print_results()
    
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(tester.results.to_dict(), f, indent=2)
        print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
