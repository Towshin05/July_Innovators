
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Evidence(Base):
    __tablename__ = "evidence"

    id = Column(Integer, primary_key=True)
    filename = Column(String, nullable=False)         
    stored_path = Column(String, nullable=False)      
    mime_type = Column(String, nullable=False)        
    file_hash = Column(String, nullable=False, index=True)  
    extracted_text = Column(Text, nullable=True)      
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    incident = relationship("Incident", back_populates="evidence", uselist=False)


class Incident(Base):
    __tablename__ = "incident"

    id = Column(Integer, primary_key=True)
    evidence_id = Column(Integer, ForeignKey("evidence.id"), nullable=False)
    category = Column(String, nullable=False)         
    location = Column(String, nullable=True)
    occurred_at = Column(DateTime, nullable=True)
    summary = Column(Text, nullable=False)            
    key_facts = Column(Text, nullable=False)          
    visual_description = Column(Text, nullable=True)   
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    evidence = relationship("Evidence", back_populates="incident")
    brief = relationship("Brief", back_populates="incident", uselist=False)


class Brief(Base):
    __tablename__ = "brief"

    id = Column(Integer, primary_key=True)
    incident_id = Column(Integer, ForeignKey("incident.id"), nullable=False, unique=True)
    headline = Column(String, nullable=False)
    body_markdown = Column(Text, nullable=False)     
    pdf_path = Column(String, nullable=True)          
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    incident = relationship("Incident", back_populates="brief")
