from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Case, TimelineEvent
from schemas.result_schema import TimelineResponse, TimelineEventSchema
from utils.logger import log_info

router = APIRouter(prefix="/cases", tags=["timeline"])


@router.get("/{case_id}/timeline", response_model=TimelineResponse)
async def get_timeline(case_id: str, db: Session = Depends(get_db)):
    """
    Get reconstructed investigation timeline
    
    Returns chronologically sorted events from all sources:
    - CCTV logs
    - GPS records
    - Metadata events
    - AI findings
    - Time of death estimates
    """
    
    case = db.query(Case).filter(Case.case_id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Fetch timeline events
    events = db.query(TimelineEvent).filter(
        TimelineEvent.case_id == case_id
    ).order_by(TimelineEvent.timestamp).all()
    
    timeline_events = [
        TimelineEventSchema(
            timestamp=e.timestamp,
            source=e.source,
            event=e.event,
            severity=e.severity,
            metadata=e.metadata_json
        )
        for e in events
    ]
    
    log_info(f"[OK] Timeline fetched for {case_id}: {len(timeline_events)} events")
    
    return TimelineResponse(
        case_id=case_id,
        events=timeline_events,
        total_events=len(timeline_events)
    )
