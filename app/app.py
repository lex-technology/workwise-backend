from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from app.middleware import RateLimitMiddleware, SecurityHeadersMiddleware
from app.routes import (
    resume,
    skills_analysis,
    summary_analysis,
    experience_analysis,
    application_process,
    cover_letter,
    auth
)

app = FastAPI()

# Add Gzip compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Add Security Headers
app.add_middleware(SecurityHeadersMiddleware)

# Add Rate Limiting
app.add_middleware(
    RateLimitMiddleware,
    rate_limit_requests=100,  # Adjust these values based on your needs
    rate_limit_window=60
)

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

# Include routers
app.include_router(resume.router, prefix="/api")
app.include_router(skills_analysis.router, prefix="/api")
app.include_router(summary_analysis.router, prefix="/api")
app.include_router(experience_analysis.router, prefix="/api")
app.include_router(application_process.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(cover_letter.router, prefix="/api")

# Add health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy"}