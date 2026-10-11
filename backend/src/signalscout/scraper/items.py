"""The data contract every spider must satisfy, whatever the source."""

from datetime import date

from pydantic import BaseModel, Field, HttpUrl, field_validator


class ArticleItem(BaseModel):
    url: HttpUrl
    url_hash: str = Field(min_length=40, max_length=40)
    source: str
    title: str = Field(min_length=5)
    author: str | None = None
    published_at: date | None = None
    text: str = Field(min_length=200)  # anything shorter is a broken selector, not an article
    outbound_links: list[str] = []

    @field_validator("title", "text")
    @classmethod
    def strip(cls, v: str) -> str:
        return v.strip()
