from typing import List, Optional
from pydantic import BaseModel, Field

class Experience(BaseModel):
    company: Optional[str]=None
    role: Optional[str]=None
    start: Optional[str]=None        # "YYYY-MM" or null
    end: Optional[str]=None
    duration_months: Optional[int]=None
    bullets: List[str]=Field(default_factory=list)

class Education(BaseModel):
    degree: Optional[str]=None
    school: Optional[str]=None
    start: Optional[str]=None
    end: Optional[str]=None

class Contacts(BaseModel):
    email: Optional[str]=None
    phone: Optional[str]=None
    location: Optional[str]=None
    links: List[str]=Field(default_factory=list)

class Profile(BaseModel):
    schema_version: str="1.0"
    source: str="cv_upload"
    name: Optional[str]=None
    contacts: Contacts=Contacts()
    summary: Optional[str]=None
    skills: List[str]=Field(default_factory=list)
    experience: List[Experience]=Field(default_factory=list)
    education: List[Education]=Field(default_factory=list)
    certs: List[str]=Field(default_factory=list)
    extras: dict=Field(default_factory=dict)
    total_duration_months: Optional[int]=0
    total_duration: Optional[str]=None