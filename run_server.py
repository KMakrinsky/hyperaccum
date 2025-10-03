#!/usr/bin/env python3
"""
Alternative server startup script using uvicorn directly
This avoids the reload warning by using the correct import string format
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
