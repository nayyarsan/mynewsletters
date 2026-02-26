import hashlib
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, computed_field


class StorySource(BaseModel):
    name: str
    url: str


class StorySummary(BaseModel):
    what_happened: str
    enterprise_impact: str
    software_delivery_impact: str
    developer_impact: str
    human_impact: str
    how_to_use: str


class Story(BaseModel):
    id: str
    title: str
    canonical_url: str
    sources: list[StorySource]
    published_at: datetime
    raw_content: str
    priority_category: Optional[str] = None
    priority_score: Optional[int] = None
    summary: Optional[StorySummary] = None

    @computed_field
    @property
    def source_count(self) -> int:
        return len(self.sources)

    @classmethod
    def from_url(
        cls,
        url: str,
        title: str,
        source_name: str,
        published_at: datetime,
        raw_content: str,
    ) -> "Story":
        story_id = hashlib.sha256(url.encode()).hexdigest()
        return cls(
            id=story_id,
            title=title,
            canonical_url=url,
            sources=[StorySource(name=source_name, url=url)],
            published_at=published_at,
            raw_content=raw_content,
        )
