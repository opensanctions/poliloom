"""Tests for the CSV source importer."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from poliloom.database import get_engine
from poliloom.importer.csv_source import (
    MissingPoliticiansError,
    _run_extractions,
    import_csv_sources,
    parse_csv_file,
)
from poliloom.models import Politician, Source


@pytest.fixture
def committed_politicians(setup_test_database):
    """Commit politicians to the test database for the importer to find.

    ``import_csv_sources`` opens its own ``Session`` and commits, so it can't
    see data from the rolled-back ``db_session`` fixture. This commits real
    rows via a callable and truncates the affected tables afterwards.
    """
    engine = setup_test_database

    def _create(*qids):
        with Session(engine) as db:
            for qid in qids:
                Politician.create_with_entity(db, qid, f"Politician {qid}")
            db.commit()

    yield _create

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE politicians, sources, wikidata_entities CASCADE"))


class TestParseCsvFile:
    """Unit tests for strict CSV parsing."""

    def test_valid_csv(self, tmp_path):
        path = tmp_path / "sources.csv"
        path.write_text(
            "qid,url\nQ42,https://example.com/foo\nQ123,https://example.org/bar\n"
        )

        result = parse_csv_file(str(path))
        assert result == [
            ("Q42", "https://example.com/foo"),
            ("Q123", "https://example.org/bar"),
        ]

    def test_uppercase_header_rejected(self, tmp_path):
        path = tmp_path / "sources.csv"
        path.write_text("QID,URL\nQ42,https://example.com\n")

        with pytest.raises(ValueError, match="header must be exactly"):
            parse_csv_file(str(path))

    def test_whitespace_header_rejected(self, tmp_path):
        path = tmp_path / "sources.csv"
        path.write_text(" qid , url \nQ42,https://example.com\n")

        with pytest.raises(ValueError, match="header must be exactly"):
            parse_csv_file(str(path))

    def test_extra_column_rejected(self, tmp_path):
        path = tmp_path / "sources.csv"
        path.write_text("qid,url,notes\nQ42,https://example.com,hi\n")

        with pytest.raises(ValueError, match="header must be exactly"):
            parse_csv_file(str(path))

    def test_reordered_header_rejected(self, tmp_path):
        path = tmp_path / "sources.csv"
        path.write_text("url,qid\nhttps://example.com,Q42\n")

        with pytest.raises(ValueError, match="header must be exactly"):
            parse_csv_file(str(path))

    def test_bom_rejected(self, tmp_path):
        path = tmp_path / "sources.csv"
        path.write_bytes(b"\xef\xbb\xbfqid,url\nQ42,https://example.com\n")

        with pytest.raises(ValueError, match="header must be exactly"):
            parse_csv_file(str(path))

    def test_wrong_column_count_rejected(self, tmp_path):
        path = tmp_path / "sources.csv"
        path.write_text("qid,url\nQ42,https://example.com,extra\n")

        with pytest.raises(ValueError, match="expected 2 columns"):
            parse_csv_file(str(path))

    def test_blank_row_rejected(self, tmp_path):
        path = tmp_path / "sources.csv"
        path.write_text(
            "qid,url\nQ42,https://example.com\n\nQ123,https://example.org\n"
        )

        with pytest.raises(ValueError, match="expected 2 columns"):
            parse_csv_file(str(path))

    def test_missing_qid_value_rejected(self, tmp_path):
        path = tmp_path / "sources.csv"
        path.write_text("qid,url\n,https://example.com\n")

        with pytest.raises(ValueError, match="invalid QID"):
            parse_csv_file(str(path))

    def test_bad_qid_rejected(self, tmp_path):
        path = tmp_path / "sources.csv"
        path.write_text("qid,url\nnot-a-qid,https://example.com\n")

        with pytest.raises(ValueError, match="invalid QID"):
            parse_csv_file(str(path))

    def test_missing_url_value_rejected(self, tmp_path):
        path = tmp_path / "sources.csv"
        path.write_text("qid,url\nQ42,\n")

        with pytest.raises(ValueError, match="invalid URL"):
            parse_csv_file(str(path))

    def test_bad_url_rejected(self, tmp_path):
        path = tmp_path / "sources.csv"
        path.write_text("qid,url\nQ42,not-a-url\n")

        with pytest.raises(ValueError, match="invalid URL"):
            parse_csv_file(str(path))

    def test_file_not_found(self):
        with pytest.raises(ValueError, match="File not found"):
            parse_csv_file("/nonexistent/path.csv")

    def test_empty_file(self, tmp_path):
        path = tmp_path / "empty.csv"
        path.write_text("")

        with pytest.raises(ValueError, match="empty"):
            parse_csv_file(str(path))

    def test_header_only_returns_no_rows(self, tmp_path):
        path = tmp_path / "sources.csv"
        path.write_text("qid,url\n")

        assert parse_csv_file(str(path)) == []


class TestRunExtractions:
    """Tests for _run_extractions."""

    async def test_calls_process_source_task_for_each_pair(self):
        task = (uuid.uuid4(), uuid.uuid4())
        tasks = [task, task]

        with patch(
            "poliloom.importer.csv_source.process_source_task",
            new_callable=AsyncMock,
        ) as mock_process:
            await _run_extractions(tasks)

        assert mock_process.call_count == 2

    async def test_handles_empty_list(self):
        with patch(
            "poliloom.importer.csv_source.process_source_task",
            new_callable=AsyncMock,
        ) as mock_process:
            await _run_extractions([])

        mock_process.assert_not_called()


class TestImportCsvSources:
    """Integration tests for the import_csv_sources orchestration."""

    def test_malformed_csv_raises(self, tmp_path):
        path = tmp_path / "bad.csv"
        path.write_text("qid,url\nbad,https://example.com\n")

        with pytest.raises(ValueError, match="invalid QID"):
            import_csv_sources(str(path))

    def test_empty_csv(self, tmp_path):
        path = tmp_path / "empty.csv"
        path.write_text("qid,url\n")

        assert import_csv_sources(str(path)) == 0

    def test_aborts_when_any_missing(self, tmp_path, committed_politicians):
        committed_politicians("Q42")
        path = tmp_path / "sources.csv"
        path.write_text("qid,url\nQ42,https://example.com\nQ999,https://example.org\n")

        with (
            patch(
                "poliloom.importer.csv_source.process_source_task",
                new_callable=AsyncMock,
            ) as mock_process,
            pytest.raises(MissingPoliticiansError) as exc_info,
        ):
            import_csv_sources(str(path))

        assert exc_info.value.qids == ["Q999"]
        mock_process.assert_not_called()
        with Session(get_engine()) as db:
            assert db.query(Source).count() == 0

    def test_dry_run_validates_only(self, tmp_path, committed_politicians):
        committed_politicians("Q42")
        path = tmp_path / "sources.csv"
        path.write_text("qid,url\nQ42,https://example.com\n")

        with patch(
            "poliloom.importer.csv_source.process_source_task",
            new_callable=AsyncMock,
        ) as mock_process:
            assert import_csv_sources(str(path), dry_run=True) == 0

        mock_process.assert_not_called()
        with Session(get_engine()) as db:
            assert db.query(Source).count() == 0

    def test_creates_and_extracts(self, tmp_path, committed_politicians):
        committed_politicians("Q42", "Q123")
        path = tmp_path / "sources.csv"
        path.write_text("qid,url\nQ42,https://example.com\nQ123,https://example.org\n")

        with patch(
            "poliloom.importer.csv_source.process_source_task",
            new_callable=AsyncMock,
        ) as mock_process:
            assert import_csv_sources(str(path)) == 2

        assert mock_process.call_count == 2
        with Session(get_engine()) as db:
            sources = db.query(Source).all()
            assert {s.url for s in sources} == {
                "https://example.com",
                "https://example.org",
            }
            by_url = {s.url: s for s in sources}
            assert {
                p.wikidata_id for p in by_url["https://example.com"].politicians
            } == {"Q42"}
            assert {
                p.wikidata_id for p in by_url["https://example.org"].politicians
            } == {"Q123"}
