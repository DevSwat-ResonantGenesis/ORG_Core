"""Stress Testing Script for ResonantGenesis Backend.

Performs stress testing by gradually increasing load until the system
reaches its breaking point, measuring maximum throughput and degradation.

Author: Agent 7 - ResonantGenesis Team
Created: February 21, 2026

Usage:
    python stress_test.py --url https://api.resonantgenesis.xyz --max-users 100 --step 10
"""

import asyncio
import aiohttp
import argparse
import time
import json
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime


@dataclass
class StressTestPhase:
    """Results from a single stress test phase."""
    concurrency: int
    duration_seconds: float
    total_requests: int
    successful_requests: int
    failed_requests: int
    requests_per_second: float
    mean_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    error_rate: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "concurrency": self.concurrency,
            "duration_seconds": round(self.duration_seconds, 2),
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "requests_per_second": round(self.requests_per_second, 2),
            "mean_latency_ms": round(self.mean_latency_ms, 2),
            "p95_latency_ms": round(self.p95_latency_ms, 2),
            "p99_latency_ms": round(self.p99_latency_ms, 2),
            "error_rate": round(self.error_rate, 4),
        }


@dataclass
class StressTestConfig:
    """Configuration for stress test."""
    base_url: str
    initial_users: int = 5
    max_users: int = 100
    step_size: int = 10
    phase_duration: int = 30
    error_threshold: float = 0.1  # 10% error rate threshold
    latency_threshold_ms: float = 5000  # 5 second latency threshold
    auth_token: Optional[str] = None


@dataclass
class StressTestResults:
    """Aggregated stress test results."""
    phases: List[StressTestPhase] = field(default_factory=list)
    breaking_point: Optional[int] = None
    max_throughput: float = 0
    optimal_concurrency: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "phases": [p.to_dict() for p in self.phases],
            "breaking_point": self.breaking_point,
            "max_throughput": round(self.max_throughput, 2),
            "optimal_concurrency": self.optimal_concurrency,
        }


class StressTester:
    """Stress testing engine."""
    
    def __init__(self, config: StressTestConfig):
        self.config = config
        self.results = StressTestResults()
        self.running = False
        self.latencies: List[float] = []
        self.successes = 0
        self.failures = 0
    
    async def _make_request(self, session: aiohttp.ClientSession) -> bool:
        """Make a single request and record result."""
        url = f"{self.config.base_url}/health"
        
        start_time = time.time()
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                latency_ms = (time.time() - start_time) * 1000
                await response.read()
                self.latencies.append(latency_ms)
                
                if 200 <= response.status < 400:
                    self.successes += 1
                    return True
                else:
                    self.failures += 1
                    return False
        except Exception:
            self.latencies.append((time.time() - start_time) * 1000)
            self.failures += 1
            return False
    
    async def _worker(self, session: aiohttp.ClientSession):
        """Worker that continuously makes requests."""
        while self.running:
            await self._make_request(session)
            await asyncio.sleep(0.01)
    
    async def _run_phase(self, concurrency: int) -> StressTestPhase:
        """Run a single stress test phase."""
        self.latencies = []
        self.successes = 0
        self.failures = 0
        self.running = True
        
        start_time = time.time()
        
        connector = aiohttp.TCPConnector(limit=concurrency * 2)
        async with aiohttp.ClientSession(connector=connector) as session:
            workers = [
                asyncio.create_task(self._worker(session))
                for _ in range(concurrency)
            ]
            
            await asyncio.sleep(self.config.phase_duration)
            
            self.running = False
            await asyncio.gather(*workers, return_exceptions=True)
        
        end_time = time.time()
        duration = end_time - start_time
        
        total_requests = self.successes + self.failures
        sorted_latencies = sorted(self.latencies) if self.latencies else [0]
        
        return StressTestPhase(
            concurrency=concurrency,
            duration_seconds=duration,
            total_requests=total_requests,
            successful_requests=self.successes,
            failed_requests=self.failures,
            requests_per_second=total_requests / duration if duration > 0 else 0,
            mean_latency_ms=sum(self.latencies) / len(self.latencies) if self.latencies else 0,
            p95_latency_ms=sorted_latencies[int(len(sorted_latencies) * 0.95)] if sorted_latencies else 0,
            p99_latency_ms=sorted_latencies[int(len(sorted_latencies) * 0.99)] if sorted_latencies else 0,
            error_rate=self.failures / total_requests if total_requests > 0 else 0,
        )
    
    async def run(self) -> StressTestResults:
        """Run the stress test."""
        print("=" * 60)
        print("STRESS TEST")
        print("=" * 60)
        print(f"URL: {self.config.base_url}")
        print(f"Initial Users: {self.config.initial_users}")
        print(f"Max Users: {self.config.max_users}")
        print(f"Step Size: {self.config.step_size}")
        print(f"Phase Duration: {self.config.phase_duration}s")
        print("=" * 60)
        print()
        
        self.results = StressTestResults()
        current_users = self.config.initial_users
        
        while current_users <= self.config.max_users:
            print(f"Phase: {current_users} concurrent users...")
            
            phase = await self._run_phase(current_users)
            self.results.phases.append(phase)
            
            # Track max throughput
            if phase.requests_per_second > self.results.max_throughput:
                self.results.max_throughput = phase.requests_per_second
                self.results.optimal_concurrency = current_users
            
            # Print phase results
            print(f"  Requests/s: {phase.requests_per_second:.2f}")
            print(f"  Mean Latency: {phase.mean_latency_ms:.2f}ms")
            print(f"  P95 Latency: {phase.p95_latency_ms:.2f}ms")
            print(f"  Error Rate: {phase.error_rate * 100:.2f}%")
            print()
            
            # Check for breaking point
            if phase.error_rate > self.config.error_threshold:
                print(f"Breaking point reached at {current_users} users (error rate > {self.config.error_threshold * 100}%)")
                self.results.breaking_point = current_users
                break
            
            if phase.p95_latency_ms > self.config.latency_threshold_ms:
                print(f"Breaking point reached at {current_users} users (latency > {self.config.latency_threshold_ms}ms)")
                self.results.breaking_point = current_users
                break
            
            current_users += self.config.step_size
        
        return self.results
    
    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 60)
        print("STRESS TEST SUMMARY")
        print("=" * 60)
        print(f"Phases Completed: {len(self.results.phases)}")
        print(f"Max Throughput: {self.results.max_throughput:.2f} req/s")
        print(f"Optimal Concurrency: {self.results.optimal_concurrency} users")
        
        if self.results.breaking_point:
            print(f"Breaking Point: {self.results.breaking_point} users")
        else:
            print("Breaking Point: Not reached")
        
        print("\nPhase Summary:")
        print("-" * 60)
        print(f"{'Users':>8} {'Req/s':>10} {'Mean(ms)':>10} {'P95(ms)':>10} {'Errors':>10}")
        print("-" * 60)
        for phase in self.results.phases:
            print(f"{phase.concurrency:>8} {phase.requests_per_second:>10.2f} {phase.mean_latency_ms:>10.2f} {phase.p95_latency_ms:>10.2f} {phase.error_rate * 100:>9.2f}%")
        print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Stress test ResonantGenesis backend")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL")
    parser.add_argument("--initial-users", type=int, default=5, help="Initial concurrent users")
    parser.add_argument("--max-users", type=int, default=100, help="Maximum concurrent users")
    parser.add_argument("--step", type=int, default=10, help="User increment per phase")
    parser.add_argument("--phase-duration", type=int, default=30, help="Duration per phase in seconds")
    parser.add_argument("--error-threshold", type=float, default=0.1, help="Error rate threshold (0-1)")
    parser.add_argument("--latency-threshold", type=float, default=5000, help="P95 latency threshold in ms")
    parser.add_argument("--token", help="Auth token")
    parser.add_argument("--output", help="Output file for JSON results")
    
    args = parser.parse_args()
    
    config = StressTestConfig(
        base_url=args.url,
        initial_users=args.initial_users,
        max_users=args.max_users,
        step_size=args.step,
        phase_duration=args.phase_duration,
        error_threshold=args.error_threshold,
        latency_threshold_ms=args.latency_threshold,
        auth_token=args.token
    )
    
    tester = StressTester(config)
    asyncio.run(tester.run())
    tester.print_summary()
    
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(tester.results.to_dict(), f, indent=2)
        print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
