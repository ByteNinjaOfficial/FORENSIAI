from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, Text, JSON
from sqlalchemy.sql import func
from database import Base
import json


class Case(Base):
    """Investigation case model"""
    __tablename__ = "cases"
    
    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(String, unique=True, index=True)
    victim_name = Column(String)
    incident_location = Column(String)
    incident_date = Column(String)
    notes = Column(Text, nullable=True)
    status = Column(String, default="pending")  # pending, processing, completed
    risk_level = Column(String, default="LOW")  # LOW, MEDIUM, HIGH
    risk_score = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class Evidence(Base):
    """Evidence file model"""
    __tablename__ = "evidence"
    
    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(String, index=True)
    file_type = Column(String)  # autopsy, cctv, gps, metadata, image
    file_name = Column(String)
    file_path = Column(String)
    processed = Column(Boolean, default=False)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())


class AIResult(Base):
    """AI analysis results model"""
    __tablename__ = "ai_results"
    
    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(String, index=True)
    agent_name = Column(String)  # autopsy_agent, correlation_agent, summary_agent
    result_json = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TimelineEvent(Base):
    """Investigation timeline events"""
    __tablename__ = "timeline_events"
    
    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(String, index=True)
    timestamp = Column(String, index=True)
    source = Column(String)  # cctv, gps, metadata, autopsy, ai
    event = Column(String)
    severity = Column(String)  # low, medium, high
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class RiskFlag(Base):
    """Risk assessment flags"""
    __tablename__ = "risk_flags"
    
    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(String, index=True)
    flag_name = Column(String)
    description = Column(String)
    score = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
