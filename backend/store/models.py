"""Skills Store Data Models"""
from typing import Optional
from pydantic import BaseModel


class RemoteSkill(BaseModel):
    """Remote skill metadata from registry."""
    name: str
    version: str
    description: str
    author: str
    category: str
    tags: list[str] = []
    downloads: int = 0
    rating: float = 0.0
    is_installed: bool = False


class SkillDetail(RemoteSkill):
    """Extended skill detail with full content."""
    readme: Optional[str] = None
    required_tools: list[str] = []
    examples: list[str] = []
    changelog: Optional[str] = None


class InstallRequest(BaseModel):
    """Request model for installing a skill."""
    skill_name: str
    version: Optional[str] = None


class InstallResponse(BaseModel):
    """Response model for skill installation."""
    status: str
    skill_name: str
    version: str
    message: str


class StoreIndexResponse(BaseModel):
    """Response model for store index."""
    version: str
    total: int
    skills: list[RemoteSkill]


class SearchParams(BaseModel):
    """Search parameters for skills."""
    q: Optional[str] = None
    category: Optional[str] = None
    page: int = 1
    page_size: int = 20
