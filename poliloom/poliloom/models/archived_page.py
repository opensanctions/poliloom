"""ArchivedPage domain models."""

import hashlib
import logging
from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    event,
    select,
    text,
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session, relationship
from sqlalchemy.orm.attributes import get_history

from ..sse import ArchivedPageStatusEvent, notify
from ..wikidata_date import WikidataDate
from .base import Base, RelationType, TimestampMixin
from .wikidata import WikidataRelation

logger = logging.getLogger(__name__)


class PoliticianArchivedPage(Base, TimestampMixin):
    """Junction table for many-to-many relationship between politicians and archived pages."""

    __tablename__ = "politician_archived_pages"

    politician_id = Column(
        UUID(as_uuid=True),
        ForeignKey("politicians.id", ondelete="CASCADE"),
        primary_key=True,
    )
    archived_page_id = Column(
        UUID(as_uuid=True),
        ForeignKey("archived_pages.id", ondelete="CASCADE"),
        primary_key=True,
    )


class ArchivedPageLanguage(Base, TimestampMixin):
    """Link table between archived pages and language entities."""

    __tablename__ = "archived_page_languages"

    archived_page_id = Column(
        UUID(as_uuid=True),
        ForeignKey("archived_pages.id", ondelete="CASCADE"),
        primary_key=True,
    )
    language_id = Column(
        String,
        ForeignKey("wikidata_entities.wikidata_id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )

    # Relationships
    archived_page = relationship(
        "ArchivedPage", back_populates="archived_page_languages"
    )
    language_entity = relationship("WikidataEntity")


class ArchivedPageError(str, Enum):
    """Error type for an archived page that failed processing."""

    FETCH_ERROR = "FETCH_ERROR"
    TIMEOUT = "TIMEOUT"
    NO_RESPONSE = "NO_RESPONSE"
    BROWSER_ERROR = "BROWSER_ERROR"
    INVALID_CONTENT = "INVALID_CONTENT"
    PIPELINE_ERROR = "PIPELINE_ERROR"


class ArchivedPageStatus(str, Enum):
    """Status of an archived page through the processing pipeline."""

    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"


class ArchivedPage(Base, TimestampMixin):
    """Archived page entity for storing fetched web page metadata."""

    __tablename__ = "archived_pages"

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    url = Column(String, nullable=False)
    permanent_url = Column(String, nullable=True)  # Wikipedia oldid URL for references
    content_hash = Column(
        String, nullable=True, index=True
    )  # SHA256 hash for deduplication, null while pending
    fetch_timestamp = Column(
        DateTime, nullable=True, default=lambda: datetime.now(timezone.utc)
    )
    user_id = Column(
        String, nullable=True, index=True
    )  # MediaWiki user ID, null = system
    wikipedia_project_id = Column(
        String,
        ForeignKey("wikipedia_projects.wikidata_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status = Column(
        SQLEnum(ArchivedPageStatus, name="archivedpagestatus"),
        nullable=False,
        server_default="PENDING",
    )
    error = Column(
        SQLEnum(ArchivedPageError, name="archivedpageerror"),
        nullable=True,
    )
    http_status_code = Column(Integer, nullable=True)
    __table_args__ = (
        CheckConstraint(
            "(error = 'FETCH_ERROR') = (http_status_code IS NOT NULL)",
            name="ck_archived_pages_http_status_code_requires_fetch_error",
        ),
    )

    # Relationships
    politicians = relationship(
        "Politician",
        secondary="politician_archived_pages",
        back_populates="archived_pages",
    )
    property_references = relationship(
        "PropertyReference", back_populates="archived_page"
    )
    archived_page_languages = relationship(
        "ArchivedPageLanguage",
        back_populates="archived_page",
        cascade="all, delete-orphan",
    )
    language_entities = relationship(
        "WikidataEntity", secondary="archived_page_languages", viewonly=True
    )
    wikipedia_project = relationship("WikipediaProject")

    @staticmethod
    def _generate_content_hash(url: str) -> str:
        """Generate a content hash for a URL."""
        return hashlib.sha256(url.encode()).hexdigest()[:16]

    @property
    def path_root(self) -> str:
        """Get the path root (timestamp/content_hash structure) for this archived page."""
        date_path = f"{self.fetch_timestamp.year:04d}/{self.fetch_timestamp.month:02d}/{self.fetch_timestamp.day:02d}"
        return f"{date_path}/{self.content_hash}"

    def link_languages_from_project(self, db) -> None:
        """Link languages from Wikipedia project's LANGUAGE_OF_WORK relations.

        Args:
            db: Database session for querying language relations
        """
        if not self.wikipedia_project_id:
            return

        language_query = select(WikidataRelation.parent_entity_id).where(
            WikidataRelation.child_entity_id == self.wikipedia_project_id,
            WikidataRelation.relation_type == RelationType.LANGUAGE_OF_WORK,
        )
        language_ids = db.execute(language_query).scalars().all()

        for language_id in language_ids:
            self.archived_page_languages.append(
                ArchivedPageLanguage(language_id=language_id)
            )

    def create_references_json(self) -> list:
        """Create references_json for this archived page source.

        For Wikipedia sources (when wikipedia_project_id exists):
        - P4656 (Wikimedia import URL) if permanent_url exists
        - P143 (imported from): Wikipedia project (e.g., Q328 for English Wikipedia)
        - P813 (retrieved): Date when the page was fetched

        For non-Wikipedia sources:
        - P854 (reference URL): The page URL
        - P813 (retrieved): Date when the page was fetched
        """
        references = []

        if self.wikipedia_project_id:
            # Wikipedia source - use permanent_url with P4656 if available
            if self.permanent_url:
                references.append(
                    {
                        "property": {"id": "P4656"},  # Wikimedia import URL
                        "value": {"type": "value", "content": self.permanent_url},
                    }
                )

            # Always add P143 (imported from) for Wikipedia sources
            references.append(
                {
                    "property": {"id": "P143"},  # Imported from
                    "value": {"type": "value", "content": self.wikipedia_project_id},
                }
            )
        else:
            # Non-Wikipedia source - use P854 (reference URL)
            references.append(
                {
                    "property": {"id": "P854"},  # Reference URL
                    "value": {"type": "value", "content": self.url},
                }
            )

        fetch_date_str = self.fetch_timestamp.strftime("%Y-%m-%d")
        wikidata_date = WikidataDate.from_date_string(fetch_date_str)
        if wikidata_date:
            references.append(
                {
                    "property": {"id": "P813"},
                    "value": {
                        "type": "value",
                        "content": wikidata_date.to_wikidata_value(),
                    },
                }
            )

        return references


@event.listens_for(ArchivedPage, "before_insert")
def generate_archived_page_content_hash(mapper, connection, target):
    """Auto-generate content_hash before inserting ArchivedPage."""
    if target.url and not target.content_hash:
        # Generate content hash from URL
        target.content_hash = ArchivedPage._generate_content_hash(target.url)


@event.listens_for(Session, "after_flush")
def _broadcast_archived_page_status(session, flush_context):
    """Broadcast SSE events when ArchivedPage status changes."""
    for obj in session.dirty | session.new:
        if not isinstance(obj, ArchivedPage):
            continue
        history = get_history(obj, "status")
        if not history.has_changes():
            continue
        notify(
            ArchivedPageStatusEvent(
                politician_ids=[str(pol.id) for pol in obj.politicians],
                archived_page_id=str(obj.id),
                status=obj.status.value,
                error=obj.error.value if obj.error else None,
                http_status_code=obj.http_status_code,
            )
        )
