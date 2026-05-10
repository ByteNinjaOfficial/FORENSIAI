from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from utils.logger import log_info

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "ForensiAI Backend",
        "version": "1.0.0"
    }


@router.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "ForensiAI - AI-Powered Forensic Investigation Platform",
        "version": "1.0.0",
        "endpoints": {
            "cases": "/docs#/cases",
            "upload": "/docs#/upload",
            "analysis": "/docs#/analysis",
            "results": "/docs#/results",
            "timeline": "/docs#/timeline"
        },
        "docs": "/docs"
    }
