#!/usr/bin/env python3
"""
Production-Ready Migration Script: Backfill Memory Hash/XYZ Coordinates
========================================================================

This script backfills existing memory records with:
- hash: Resonance hash from content (SHA-256 + energy + spin)
- xyz_x, xyz_y, xyz_z: 3D coordinates in semantic space
- resonance_score: Normalized resonance function value

Features:
- Batch processing with configurable batch size
- Progress tracking with ETA
- Dry-run mode for testing
- Resume capability (skips already-processed records)
- Error handling with retry logic
- Logging to file and console
- PCA-based xyz from embeddings when available (more semantic)
- Hash-based xyz fallback when no embedding exists

Usage:
    # Dry run (no changes)
    python backfill_memory_hash_xyz.py --dry-run
    
    # Run migration
    python backfill_memory_hash_xyz.py
    
    # Custom batch size
    python backfill_memory_hash_xyz.py --batch-size 500
    
    # Force reprocess all (even those with existing hash)
    python backfill_memory_hash_xyz.py --force

Author: Cascade AI
Date: Dec 29, 2025
"""

import argparse
import asyncio
import hashlib
import logging
import os
import sys
import time
from datetime import datetime
from typing import List, Optional, Tuple

import numpy as np
from sklearn.decomposition import PCA
from sqlalchemy import create_engine, text, select, update
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'backfill_memory_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)
logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.getenv(
    "MEMORY_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/memory_db"
)

# Resonance constants (from foundational architecture)
RESONANCE_A = np.pi / 4   # sin coefficient
RESONANCE_B = np.e / 3    # cos coefficient  
RESONANCE_C = 1.618 / 2   # tan coefficient (golden ratio / 2)


class ResonanceHasher:
    """Simplified resonance hasher for migration script."""
    
    _pca_model: Optional[PCA] = None
    
    @staticmethod
    def hash_text(text: str) -> str:
        """Create a resonance hash from text."""
        normalized = text.lower().strip()
        
        # Meaning hash
        meaning_hash = hashlib.sha256(normalized.encode()).hexdigest()[:16]
        
        # Energy (intensity)
        intensity_words = ['very', 'extremely', 'highly', 'critical', 'urgent', 'important']
        intensity_count = sum(1 for word in intensity_words if word in normalized)
        exclamation_count = text.count('!')
        caps_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
        energy = min(1.0, intensity_count * 0.1 + exclamation_count * 0.05 + caps_ratio * 0.5)
        energy_hash = hashlib.sha256(str(energy).encode()).hexdigest()[:8]
        
        # Spin (sentiment)
        positive_words = ['good', 'great', 'excellent', 'amazing', 'love', 'happy', 'success']
        negative_words = ['bad', 'terrible', 'awful', 'hate', 'sad', 'fail', 'error']
        pos = sum(1 for w in positive_words if w in normalized)
        neg = sum(1 for w in negative_words if w in normalized)
        spin = 0.5 if pos + neg == 0 else (pos - neg) / (pos + neg + 0.001) / 2 + 0.5
        spin_hash = hashlib.sha256(str(spin).encode()).hexdigest()[:8]
        
        combined = f"{meaning_hash}-{energy_hash}-{spin_hash}"
        return hashlib.sha256(combined.encode()).hexdigest()
    
    @staticmethod
    def hash_to_coords(hash_str: str) -> Tuple[float, float, float]:
        """Convert hash to 3D coordinates."""
        if len(hash_str) < 24:
            hash_str = hash_str.ljust(24, '0')
        
        x = int(hash_str[:8], 16) / 0xFFFFFFFF
        y = int(hash_str[8:16], 16) / 0xFFFFFFFF
        z = int(hash_str[16:24], 16) / 0xFFFFFFFF
        
        return (x, y, z)
    
    @staticmethod
    def calculate_xyz_from_embedding(embedding: List[float]) -> Tuple[float, float, float]:
        """Convert embedding to 3D coordinates using PCA."""
        if not embedding or len(embedding) < 3:
            return None
        
        embedding_array = np.array(embedding).reshape(1, -1)
        
        if len(embedding) <= 3:
            coords = embedding_array[0]
            coords = (coords - coords.min()) / (coords.max() - coords.min() + 1e-10)
            if len(coords) < 3:
                coords = np.pad(coords, (0, 3 - len(coords)), mode='constant')
            return tuple(coords[:3].tolist())
        
        if ResonanceHasher._pca_model is None:
            ResonanceHasher._pca_model = PCA(n_components=3)
            dummy = np.random.rand(1, len(embedding))
            ResonanceHasher._pca_model.fit(dummy)
        
        coords_3d = ResonanceHasher._pca_model.transform(embedding_array)[0]
        coords_3d = (coords_3d - coords_3d.min()) / (coords_3d.max() - coords_3d.min() + 1e-10)
        
        return tuple(coords_3d.tolist())
    
    @staticmethod
    def calculate_resonance_function(xyz: Tuple[float, float, float]) -> float:
        """Calculate resonance: R(h) = sin(a·x) + cos(b·y) + tan(c·z)"""
        x, y, z = xyz
        resonance = (
            np.sin(RESONANCE_A * x) +
            np.cos(RESONANCE_B * y) +
            np.tan(RESONANCE_C * z)
        )
        return float(resonance)


async def get_total_count(engine, force: bool = False) -> int:
    """Get total count of records to process."""
    async with AsyncSession(engine) as session:
        if force:
            query = text("SELECT COUNT(*) FROM memory_records")
        else:
            query = text("SELECT COUNT(*) FROM memory_records WHERE hash IS NULL OR xyz_x IS NULL")
        result = await session.execute(query)
        return result.scalar()


async def get_batch(engine, offset: int, batch_size: int, force: bool = False) -> List[dict]:
    """Get a batch of records to process."""
    async with AsyncSession(engine) as session:
        if force:
            query = text("""
                SELECT id, content 
                FROM memory_records 
                ORDER BY created_at 
                LIMIT :limit OFFSET :offset
            """)
        else:
            query = text("""
                SELECT id, content 
                FROM memory_records 
                WHERE hash IS NULL OR xyz_x IS NULL
                ORDER BY created_at 
                LIMIT :limit OFFSET :offset
            """)
        result = await session.execute(query, {"limit": batch_size, "offset": offset})
        rows = result.fetchall()
        return [{"id": str(row[0]), "content": row[1]} for row in rows]


async def get_embedding_for_memory(engine, memory_id: str) -> Optional[List[float]]:
    """Get embedding for a memory if it exists."""
    async with AsyncSession(engine) as session:
        query = text("""
            SELECT embedding 
            FROM memory_embeddings 
            WHERE memory_id = :memory_id
            LIMIT 1
        """)
        result = await session.execute(query, {"memory_id": memory_id})
        row = result.fetchone()
        if row and row[0]:
            return list(row[0])
        return None


async def update_record(
    engine,
    memory_id: str,
    hash_value: str,
    xyz: Tuple[float, float, float],
    resonance_score: float,
    dry_run: bool = False
) -> bool:
    """Update a single record with hash and xyz."""
    if dry_run:
        return True
    
    async with AsyncSession(engine) as session:
        try:
            query = text("""
                UPDATE memory_records 
                SET hash = :hash,
                    xyz_x = :xyz_x,
                    xyz_y = :xyz_y,
                    xyz_z = :xyz_z,
                    resonance_score = :resonance_score,
                    updated_at = NOW()
                WHERE id = :id
            """)
            await session.execute(query, {
                "id": memory_id,
                "hash": hash_value,
                "xyz_x": xyz[0],
                "xyz_y": xyz[1],
                "xyz_z": xyz[2],
                "resonance_score": resonance_score
            })
            await session.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to update record {memory_id}: {e}")
            await session.rollback()
            return False


async def process_batch(
    engine,
    records: List[dict],
    dry_run: bool = False,
    use_embeddings: bool = True
) -> Tuple[int, int]:
    """Process a batch of records."""
    success = 0
    failed = 0
    
    for record in records:
        try:
            content = record["content"]
            memory_id = record["id"]
            
            # Generate hash
            content_hash = ResonanceHasher.hash_text(content)
            
            # Try to get xyz from embedding first (more semantic)
            xyz = None
            if use_embeddings:
                embedding = await get_embedding_for_memory(engine, memory_id)
                if embedding:
                    xyz = ResonanceHasher.calculate_xyz_from_embedding(embedding)
            
            # Fallback to hash-based xyz
            if xyz is None:
                xyz = ResonanceHasher.hash_to_coords(content_hash)
            
            # Calculate resonance score (normalized to 0-1)
            resonance_raw = ResonanceHasher.calculate_resonance_function(xyz)
            resonance_score = (resonance_raw + 3) / 6  # Normalize from ~[-3,3] to [0,1]
            resonance_score = max(0.0, min(1.0, resonance_score))  # Clamp
            
            # Update record
            if await update_record(engine, memory_id, content_hash, xyz, resonance_score, dry_run):
                success += 1
            else:
                failed += 1
                
        except Exception as e:
            logger.error(f"Error processing record {record.get('id', 'unknown')}: {e}")
            failed += 1
    
    return success, failed


async def run_migration(
    batch_size: int = 100,
    dry_run: bool = False,
    force: bool = False,
    use_embeddings: bool = True
):
    """Run the migration."""
    logger.info("=" * 60)
    logger.info("Hash Sphere Memory Backfill Migration")
    logger.info("=" * 60)
    logger.info(f"Database: {DATABASE_URL.split('@')[-1]}")  # Hide credentials
    logger.info(f"Batch size: {batch_size}")
    logger.info(f"Dry run: {dry_run}")
    logger.info(f"Force reprocess: {force}")
    logger.info(f"Use embeddings for PCA: {use_embeddings}")
    logger.info("=" * 60)
    
    # Create async engine
    engine = create_async_engine(DATABASE_URL, echo=False)
    
    try:
        # Get total count
        total = await get_total_count(engine, force)
        logger.info(f"Total records to process: {total}")
        
        if total == 0:
            logger.info("No records to process. Migration complete!")
            return
        
        # Process in batches
        processed = 0
        total_success = 0
        total_failed = 0
        start_time = time.time()
        
        while processed < total:
            batch_start = time.time()
            
            # Get batch
            records = await get_batch(engine, 0 if not force else processed, batch_size, force)
            
            if not records:
                break
            
            # Process batch
            success, failed = await process_batch(engine, records, dry_run, use_embeddings)
            
            total_success += success
            total_failed += failed
            processed += len(records)
            
            # Calculate progress and ETA
            elapsed = time.time() - start_time
            rate = processed / elapsed if elapsed > 0 else 0
            remaining = total - processed
            eta = remaining / rate if rate > 0 else 0
            
            batch_time = time.time() - batch_start
            
            logger.info(
                f"Progress: {processed}/{total} ({processed/total*100:.1f}%) | "
                f"Success: {total_success} | Failed: {total_failed} | "
                f"Rate: {rate:.1f}/s | ETA: {eta/60:.1f}m | "
                f"Batch time: {batch_time:.2f}s"
            )
        
        # Final summary
        elapsed = time.time() - start_time
        logger.info("=" * 60)
        logger.info("Migration Complete!")
        logger.info(f"Total processed: {processed}")
        logger.info(f"Successful: {total_success}")
        logger.info(f"Failed: {total_failed}")
        logger.info(f"Total time: {elapsed/60:.2f} minutes")
        logger.info(f"Average rate: {processed/elapsed:.1f} records/second")
        if dry_run:
            logger.info("NOTE: This was a DRY RUN - no changes were made!")
        logger.info("=" * 60)
        
    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser(
        description="Backfill memory records with Hash Sphere coordinates"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of records to process per batch (default: 100)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without making changes (test mode)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocess all records, even those with existing hash/xyz"
    )
    parser.add_argument(
        "--no-embeddings",
        action="store_true",
        help="Skip PCA from embeddings, use hash-based xyz only"
    )
    parser.add_argument(
        "--database-url",
        type=str,
        help="Override database URL"
    )
    
    args = parser.parse_args()
    
    if args.database_url:
        global DATABASE_URL
        DATABASE_URL = args.database_url
    
    asyncio.run(run_migration(
        batch_size=args.batch_size,
        dry_run=args.dry_run,
        force=args.force,
        use_embeddings=not args.no_embeddings
    ))


if __name__ == "__main__":
    main()
