#!/usr/bin/env python3
"""
CASCADE Control Plane - Run Script
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8095,
        log_level="info"
    )
