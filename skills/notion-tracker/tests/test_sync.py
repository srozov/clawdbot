#!/usr/bin/env python3
"""Tests for notion-tracker skill."""
import pytest
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

from notion_tracker.models import (
    ApplicationInput,
    ApplicationStatus,
    SyncResult,
    SyncSummary,
    SyncStatus,
    NotionConfig,
    OAuthTokenData,
)


class TestApplicationInput:
    """Test ApplicationInput model."""

    def test_create_application_input(self):
        """Test creating an application input."""
        app = ApplicationInput(
            company="Google",
            title="Senior Engineer",
            location="Zürich",
            match_score=0.85,
            match_reasoning="Strong Python skills",
            key_matches=["Python", "Django"],
            missing_skills=["Kubernetes"],
        )

        assert app.company == "Google"
        assert app.title == "Senior Engineer"
        assert app.location == "Zürich"
        assert app.match_score == 0.85
        assert "Python" in app.key_matches
        assert "Kubernetes" in app.missing_skills

    def test_application_input_defaults(self):
        """Test application input default values."""
        app = ApplicationInput(company="Test", title="Developer")

        assert app.match_score == 0.0
        assert app.status == "Not Applied"
        assert app.key_matches == []
        assert app.missing_skills == []


class TestSyncResult:
    """Test SyncResult model."""

    def test_sync_result_pending(self):
        """Test pending sync result."""
        result = SyncResult(
            job_id="Google_Senior_Engineer",
            company="Google",
            title="Senior Engineer"
        )

        assert result.status == SyncStatus.PENDING
        assert result.notion_page_id is None
        assert result.error is None

    def test_sync_result_synced(self):
        """Test synced sync result."""
        result = SyncResult(
            job_id="Google_Senior_Engineer",
            company="Google",
            title="Senior Engineer",
            notion_page_id="abc123",
            status=SyncStatus.SYNCED,
            synced_at=datetime.now()
        )

        assert result.status == SyncStatus.SYNCED
        assert result.notion_page_id == "abc123"


class TestSyncSummary:
    """Test SyncSummary model."""

    def test_sync_summary(self):
        """Test sync summary with results."""
        results = [
            SyncResult(job_id="a", company="A", title="T1", status=SyncStatus.SYNCED),
            SyncResult(job_id="b", company="B", title="T2", status=SyncStatus.SKIPPED),
            SyncResult(job_id="c", company="C", title="T3", status=SyncStatus.FAILED, error="Error"),
        ]

        summary = SyncSummary(
            total_applications=3,
            synced=1,
            skipped=1,
            failed=1,
            results=results
        )

        assert summary.total_applications == 3
        assert summary.synced == 1
        assert summary.skipped == 1
        assert summary.failed == 1


class TestNotionConfig:
    """Test NotionConfig model."""

    def test_notion_config_defaults(self):
        """Test default config values."""
        config = NotionConfig(database_id="test-id")

        assert config.database_id == "test-id"
        assert config.oauth_enabled is True
        assert config.sync_mode == "incremental"
        assert config.rate_limit_delay == 0.35
        assert config.max_retries == 3


class TestOAuthTokenData:
    """Test OAuthTokenData model."""

    def test_oauth_token_data(self):
        """Test OAuth token data."""
        token = OAuthTokenData(
            access_token="test-token",
            refresh_token="refresh-token",
            expires_in=3600,
            issued_at=1234567890
        )

        assert token.access_token == "test-token"
        assert token.token_type == "bearer"


class TestApplicationStatus:
    """Test ApplicationStatus enum."""

    def test_status_values(self):
        """Test all status values."""
        assert ApplicationStatus.NOT_APPLIED.value == "Not Applied"
        assert ApplicationStatus.APPLIED.value == "Applied"
        assert ApplicationStatus.INTERVIEW_SCHEDULED.value == "Interview Scheduled"
        assert ApplicationStatus.REJECTED.value == "Rejected"
        assert ApplicationStatus.OFFER.value == "Offer"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
