from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import (
    resume,
    skills_analysis,
    summary_analysis,
    experience_analysis,
    application_process,
    cover_letter,
    auth
)
from app.routes.auth import router as auth_router

app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(resume.router, prefix="/api")
app.include_router(skills_analysis.router, prefix="/api")
app.include_router(summary_analysis.router, prefix="/api")
app.include_router(experience_analysis.router, prefix="/api")
app.include_router(application_process.router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(cover_letter.router, prefix="/api")
