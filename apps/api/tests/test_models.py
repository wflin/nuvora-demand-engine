"""Real-PostgreSQL tests for the Research data models.

Each test runs inside a session transaction that is rolled back afterwards,
so no test data is ever committed to the development database.
"""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal
from app.models import (
    Keyword,
    KeywordMetricSnapshot,
    ResearchKeyword,
    ResearchProject,
)
from app.models.keywords import normalize_keyword


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def make_research(**overrides):
    values = {
        "name": "Invoice software research",
        "seed_keyword": "invoice",
        "country_code": "US",
        "language_code": "en",
        "status": "draft",
    }
    values.update(overrides)
    return ResearchProject(**values)


def make_keyword(**overrides):
    values = {
        "keyword_text": "best keyword tool",
        "normalized_keyword": "best keyword tool",
        "language_code": "en",
    }
    values.update(overrides)
    return Keyword(**values)


def test_normalize_keyword_is_deterministic() -> None:
    assert normalize_keyword("  Best   Keyword  TOOL ") == "best keyword tool"
    assert normalize_keyword("AI工具") == "ai工具"
    assert normalize_keyword("C++ tutorial") == "c++ tutorial"
    assert normalize_keyword("上海 中考 数学") == "上海 中考 数学"


def test_research_project_create_and_read(db) -> None:
    research = make_research()
    db.add(research)
    db.flush()

    assert isinstance(research.id, uuid.UUID)
    assert research.created_at.tzinfo is not None
    assert research.updated_at.tzinfo is not None

    loaded = db.get(ResearchProject, research.id)
    assert loaded is not None
    assert loaded.name == "Invoice software research"
    assert loaded.seed_keyword == "invoice"
    assert loaded.country_code == "US"
    assert loaded.language_code == "en"
    assert loaded.status == "draft"
    assert loaded.description is None


def test_keyword_create_and_read_with_unicode(db) -> None:
    keyword = make_keyword(
        keyword_text="AI工具",
        normalized_keyword=normalize_keyword("AI工具"),
        language_code=None,
    )
    db.add(keyword)
    db.flush()

    assert isinstance(keyword.id, uuid.UUID)
    loaded = db.get(Keyword, keyword.id)
    assert loaded is not None
    assert loaded.keyword_text == "AI工具"
    assert loaded.normalized_keyword == "ai工具"
    assert loaded.language_code is None


def test_research_keyword_association_and_navigation(db) -> None:
    research = make_research()
    keyword = make_keyword()
    db.add_all([research, keyword])
    db.flush()

    link = ResearchKeyword(
        research_id=research.id,
        keyword_id=keyword.id,
        source_type="seed",
    )
    db.add(link)
    db.flush()

    assert research.research_keywords == [link]
    assert keyword.research_keywords == [link]
    assert link.research is research
    assert link.keyword is keyword


def test_research_keyword_unique_constraint(db) -> None:
    research = make_research()
    keyword = make_keyword()
    db.add_all([research, keyword])
    db.flush()

    db.add(
        ResearchKeyword(
            research_id=research.id,
            keyword_id=keyword.id,
            source_type="seed",
        )
    )
    db.flush()

    db.add(
        ResearchKeyword(
            research_id=research.id,
            keyword_id=keyword.id,
            source_type="provider",
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()


def test_keyword_metric_snapshot_allows_null_metrics(db) -> None:
    research = make_research()
    keyword = make_keyword()
    db.add_all([research, keyword])
    db.flush()

    snapshot = KeywordMetricSnapshot(
        keyword_id=keyword.id,
        research_id=research.id,
        country_code="US",
        language_code="en",
        source="manual",
    )
    db.add(snapshot)
    db.flush()

    loaded = db.get(KeywordMetricSnapshot, snapshot.id)
    assert loaded is not None
    assert loaded.estimated_monthly_searches is None
    assert loaded.cpc is None
    assert loaded.competition is None
    assert loaded.currency is None
    assert loaded.competition_level is None
    assert loaded.provider_version is None
    assert loaded.raw_payload is None


def test_keyword_metric_snapshot_persists_values(db) -> None:
    research = make_research()
    keyword = make_keyword()
    db.add_all([research, keyword])
    db.flush()

    snapshot = KeywordMetricSnapshot(
        keyword_id=keyword.id,
        research_id=research.id,
        country_code="US",
        language_code="en",
        source="sample_source",
        estimated_monthly_searches=12000,
        cpc=Decimal("1.2300"),
        currency="USD",
        competition=Decimal("0.4500"),
        competition_level="medium",
        provider_version="1.0",
        raw_payload={"note": "sample"},
    )
    db.add(snapshot)
    db.flush()

    loaded = db.get(KeywordMetricSnapshot, snapshot.id)
    assert loaded is not None
    assert loaded.estimated_monthly_searches == 12000
    assert loaded.cpc == Decimal("1.2300")
    assert loaded.currency == "USD"
    assert loaded.competition == Decimal("0.4500")
    assert loaded.raw_payload == {"note": "sample"}
    assert keyword.metric_snapshots == [snapshot]


def test_foreign_key_violation_for_missing_research(db) -> None:
    keyword = make_keyword()
    db.add(keyword)
    db.flush()

    db.add(
        ResearchKeyword(
            research_id=uuid.uuid4(),
            keyword_id=keyword.id,
            source_type="seed",
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()


def test_deleting_research_removes_links_but_keeps_keyword(db) -> None:
    research = make_research()
    keyword = make_keyword()
    db.add_all([research, keyword])
    db.flush()

    link = ResearchKeyword(
        research_id=research.id,
        keyword_id=keyword.id,
        source_type="seed",
    )
    db.add(link)
    db.flush()

    db.delete(research)
    db.flush()

    assert db.scalar(select(ResearchKeyword).where(ResearchKeyword.id == link.id)) is None
    assert db.get(Keyword, keyword.id) is not None


def test_database_on_delete_cascade_for_link(db) -> None:
    research = make_research()
    keyword = make_keyword()
    db.add_all([research, keyword])
    db.flush()

    link = ResearchKeyword(
        research_id=research.id,
        keyword_id=keyword.id,
        source_type="seed",
    )
    db.add(link)
    db.flush()

    db.execute(
        text("DELETE FROM research_project WHERE id = :id"),
        {"id": research.id},
    )
    db.flush()

    assert db.scalar(select(ResearchKeyword).where(ResearchKeyword.id == link.id)) is None