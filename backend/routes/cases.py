from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pathlib import Path
from database import get_db
from models import Case, Evidence, AIResult, TimelineEvent, RiskFlag
from config import settings
from schemas.case_schema import CaseCreate, CaseResponse, CaseDetailResponse
from utils.helpers import generate_case_id
from utils.logger import log_info, log_error
from datetime import datetime

router = APIRouter(prefix="/cases", tags=["cases"])


@router.post("", response_model=CaseResponse)
async def create_case(case_data: CaseCreate, db: Session = Depends(get_db)):
    """Create a new investigation case"""
    
    case_id = generate_case_id()
    
    case = Case(
        case_id=case_id,
        victim_name=case_data.victim_name,
        incident_location=case_data.incident_location,
        incident_date=case_data.incident_date,
        notes=case_data.notes,
        status="pending",
        risk_level="LOW",
        risk_score=0.0
    )
    
    db.add(case)
    db.commit()
    db.refresh(case)
    
    log_info(f"[OK] Case created: {case_id}")
    
    return case


@router.get("", response_model=list[CaseResponse])
async def list_cases(db: Session = Depends(get_db)):
    """List all investigation cases"""
    
    cases = db.query(Case).order_by(Case.created_at.desc()).all()
    
    return cases


@router.get("/{case_id}", response_model=CaseDetailResponse)
async def get_case(case_id: str, db: Session = Depends(get_db)):
    """Get case details"""
    
    case = db.query(Case).filter(Case.case_id == case_id).first()
    
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    return case


@router.put("/{case_id}")
async def update_case_notes(case_id: str, notes: str, db: Session = Depends(get_db)):
    """Update case notes"""
    
    case = db.query(Case).filter(Case.case_id == case_id).first()
    
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    case.notes = notes
    case.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(case)
    
    log_info(f"[OK] Case notes updated: {case_id}")
    
    return {"message": "Case updated", "case": case}


@router.delete("/{case_id}")
async def delete_case(case_id: str, db: Session = Depends(get_db)):
    """Delete a case and all associated data"""
    
    case = db.query(Case).filter(Case.case_id == case_id).first()
    
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    evidence_files = db.query(Evidence).filter(Evidence.case_id == case_id).all()
    upload_root = Path(settings.upload_dir).resolve()

    for evidence in evidence_files:
        try:
            path = Path(evidence.file_path).resolve()
            if upload_root in path.parents and path.exists():
                path.unlink()
        except Exception as e:
            log_error(f"Unable to delete evidence file for {case_id}", e)

    db.query(TimelineEvent).filter(TimelineEvent.case_id == case_id).delete(synchronize_session=False)
    db.query(AIResult).filter(AIResult.case_id == case_id).delete(synchronize_session=False)
    db.query(RiskFlag).filter(RiskFlag.case_id == case_id).delete(synchronize_session=False)
    db.query(Evidence).filter(Evidence.case_id == case_id).delete(synchronize_session=False)
    db.delete(case)
    db.commit()

    case_upload_dir = upload_root / case_id
    try:
        if case_upload_dir.exists() and not any(case_upload_dir.iterdir()):
            case_upload_dir.rmdir()
    except Exception as e:
        log_error(f"Unable to remove empty upload directory for {case_id}", e)
    
    log_info(f"[OK] Case deleted: {case_id}")
    
    return {"message": f"Case {case_id} successfully deleted"}
