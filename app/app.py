from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
import time
from app.routes import (
    resume,
    skills_analysis,
    summary_analysis,
    experience_analysis,
    application_process,
    cover_letter,
    auth
)
from fastapi.middleware.gzip import GZipMiddleware

app = FastAPI()

# Add Gzip compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# CORS middleware with more specific configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://workwise-frontend-amber.vercel.app",
        "https://workwise-frontend-git-main-liong-cheng-lexs-projects.vercel.app",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "Origin",
        "X-Requested-With",
    ],
    expose_headers=["*"],
    max_age=3600,
)

# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Include routers
app.include_router(resume.router, prefix="/api")
app.include_router(skills_analysis.router, prefix="/api")
app.include_router(summary_analysis.router, prefix="/api")
app.include_router(experience_analysis.router, prefix="/api")
app.include_router(application_process.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(cover_letter.router, prefix="/api")

# Error handling
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return Response(
        status_code=500,
        content={"detail": str(exc)}
    )