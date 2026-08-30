"""
test_security.py — Phase 4: Row-Level Security & Access Control
"""

import pytest
from backend.security import parse_user_context, get_access_log
from backend.database import secure_query
from backend.models import UserContext


def test_parse_user_context_ceo():
    user = parse_user_context("CEO")
    assert user.role == "ceo" or user.role == "executive"
    assert "ALL" in user.allowed_regions or user.allowed_regions == ["all"]
    assert user.can_view_pii is True


def test_parse_user_context_regional_manager_west():
    user = parse_user_context("Regional_Manager_West")
    assert user.role == "regional_manager"
    assert "West" in user.allowed_regions
    assert "East" not in user.allowed_regions
    assert user.can_view_pii is False


def test_parse_user_context_unknown_defaults_to_ceo():
    user = parse_user_context("unknown_user_xyz")
    assert user.user_id == "CEO"
    assert user.can_view_pii is True


def test_parse_user_context_none_defaults_to_ceo():
    user = parse_user_context(None)
    assert user.user_id == "CEO"


def test_rls_west_cannot_see_east_data(db):
    """Regional Manager West must never receive East region rows."""
    west_user = UserContext(
        user_id="Regional_Manager_West",
        role="regional_manager",
        name="Regional Manager West",
        allowed_regions=["West"],
        can_view_pii=False,
    )
    cursor = db.cursor()
    try:
        df = secure_query(
            cursor,
            "SELECT * FROM sales_transactions",
            params={},
            user_context=west_user,
        )
        if not df.empty and "region" in df.columns:
            regions_returned = df["region"].unique().tolist()
            assert "East" not in regions_returned, (
                f"West RM should not see East rows. Got regions: {regions_returned}"
            )
            assert "North" not in regions_returned
            assert "South" not in regions_returned
    finally:
        cursor.close()


def test_rls_ceo_sees_all_regions(db):
    """CEO with allowed_regions=['ALL'] must see all regions."""
    ceo_user = UserContext(
        user_id="CEO",
        role="ceo",
        name="CEO",
        allowed_regions=["ALL"],
        can_view_pii=True,
    )
    cursor = db.cursor()
    try:
        df = secure_query(
            cursor,
            "SELECT DISTINCT region FROM sales_transactions",
            params={},
            user_context=ceo_user,
        )
        assert not df.empty
        regions = df["region"].tolist()
        assert "West" in regions
        assert "East" in regions
    finally:
        cursor.close()


def test_pii_redacted_for_regional_manager(db):
    """nps_comment column must be REDACTED for non-PII users."""
    rm_user = UserContext(
        user_id="Regional_Manager_West",
        role="regional_manager",
        name="Regional Manager West",
        allowed_regions=["West"],
        can_view_pii=False,
    )
    cursor = db.cursor()
    try:
        df = secure_query(
            cursor,
            "SELECT * FROM customer_events",
            params={},
            user_context=rm_user,
        )
        if not df.empty and "nps_comment" in df.columns:
            non_empty = df[df["nps_comment"] != ""]["nps_comment"].unique()
            assert all(v == "REDACTED" for v in non_empty), (
                f"Non-empty nps_comment values for RM should all be REDACTED: {non_empty}"
            )
    finally:
        cursor.close()


def test_pii_visible_for_ceo(db):
    """CEO with can_view_pii=True must see actual nps_comment values."""
    ceo_user = UserContext(
        user_id="CEO",
        role="ceo",
        name="CEO",
        allowed_regions=["ALL"],
        can_view_pii=True,
    )
    cursor = db.cursor()
    try:
        df = secure_query(
            cursor,
            "SELECT nps_comment FROM customer_events WHERE nps_comment != ''",
            params={},
            user_context=ceo_user,
        )
        if not df.empty:
            assert not all(v == "REDACTED" for v in df["nps_comment"]), (
                "CEO should see real PII, not REDACTED"
            )
    finally:
        cursor.close()


def test_access_log_records_query(db):
    """Every secure_query call should append a row to the access_log."""
    rm_user = UserContext(
        user_id="test_audit_user",
        role="regional_manager",
        name="Test User",
        allowed_regions=["West"],
        can_view_pii=False,
    )
    cursor = db.cursor()
    try:
        # Count before; query must have a region column so the RLS wrapper can filter
        before = cursor.execute("SELECT COUNT(*) FROM access_log").fetchone()[0]
        secure_query(cursor, "SELECT * FROM sales_transactions LIMIT 5", params={}, user_context=rm_user)
        after = cursor.execute("SELECT COUNT(*) FROM access_log").fetchone()[0]
        assert after > before, "access_log should grow after a secure_query call"
    finally:
        cursor.close()
