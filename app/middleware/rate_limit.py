# app/middleware/rate_limit.py
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
import time
from collections import defaultdict

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: FastAPI,
        rate_limit_requests: int = 100,  # Number of requests
        rate_limit_window: int = 60,     # Time window in seconds
    ):
        super().__init__(app)
        self.rate_limit_requests = rate_limit_requests
        self.rate_limit_window = rate_limit_window
        self.request_counts = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        # Get client IP
        client_ip = request.client.host
        
        # Clean old requests
        current_time = time.time()
        self.request_counts[client_ip] = [
            req_time for req_time in self.request_counts[client_ip]
            if current_time - req_time < self.rate_limit_window
        ]
        
        # Check rate limit
        if len(self.request_counts[client_ip]) >= self.rate_limit_requests:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests"}
            )
        
        # Add new request
        self.request_counts[client_ip].append(current_time)
        
        # Process request
        response = await call_next(request)
        return response