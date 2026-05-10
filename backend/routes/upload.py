from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from pathlib import Path
import shutil
import os
from database import get_db
from models import Case, Evidence
from config import settings
from utils.logger import log_info, log_error
from schemas.evidence_schema import EvidenceResponse

router = APIRouter(prefix="/cases", tags=["upload"])


@router.post("/{case_id}/upload", response_model=dict)
async def upload_evidence(
    case_id: str,
    file: UploadFile = File(...),
    file_type: str = Form(...),
    db: Session = Depends(get_db)
):
    """Upload evidence file for a case"""
    
    # Verify case exists
    case = db.query(Case).filter(Case.case_id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Validate file type
    valid_types = ["autopsy", "cctv", "gps", "metadata", "image"]
    if file_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Must be one of: {', '.join(valid_types)}"
        )
    
    # Create case upload directory
    case_upload_dir = Path(settings.upload_dir) / case_id
    case_upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Save file
    file_path = case_upload_dir / file.filename
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        log_error(f"File upload failed for {file.filename}", e)
        raise HTTPException(status_code=500, detail="File upload failed")
    
    # Create evidence record
    evidence = Evidence(
        case_id=case_id,
        file_type=file_type,
        file_name=file.filename,
        file_path=str(file_path),
        processed=False
    )
    
    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    
    log_info(f"[OK] Evidence uploaded: {file.filename} ({file_type}) for case {case_id}")
    
    return {
        "message": "File uploaded successfully",
        "file_name": file.filename,
        "file_type": file_type,
        "case_id": case_id,
        "file_path": str(file_path)
    }


@router.get("/{case_id}/evidence", response_model=list[EvidenceResponse])
async def list_evidence(case_id: str, db: Session = Depends(get_db)):
    """List all evidence for a case"""
    
    # Verify case exists
    case = db.query(Case).filter(Case.case_id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    evidence = db.query(Evidence).filter(
        Evidence.case_id == case_id
    ).order_by(Evidence.uploaded_at.desc()).all()
    
    return evidence
