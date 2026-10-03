from __future__ import annotations

from typing import Any

import pytest

from tests.conftest import SessionHandle
from tests.factories import EXAMPLE_PATCH


def test_patch_records_edits_as_confirmed(session: SessionHandle) -> None:
    response = session.patch({"support_years": 15})
    assert response.status_code == 200
    assert response.json()["profile"]["support_years"] == {
        "value": 15,
        "source": "edited",
        "confirmed": True,
    }


def test_patch_null_means_unknown(session: SessionHandle) -> None:
    body = session.patch({"personal_coverage": None}).json()
    assert body["profile"]["personal_coverage"]["value"] is None


def test_patch_confirm_keeps_value_and_source(session: SessionHandle) -> None:
    session.say("3")
    body = session.patch(confirm=["dependents_count"]).json()
    assert body["profile"]["dependents_count"] == {
        "value": 3,
        "source": "stated",
        "confirmed": True,
    }


def test_cannot_confirm_unanswered_field(session: SessionHandle) -> None:
    response = session.patch(confirm=["support_years"])
    assert response.status_code == 422


@pytest.mark.parametrize(
    "updates",
    [
        {"annual_support_need": 80_000.5},
        {"annual_support_need": -5},
        {"annual_support_need": "80000"},
        {"made_up_field": 1},
        {
            "one_time_expenses": [
                {"id": "a", "label": "A", "category": "education", "amount": 1},
                {"id": "b", "label": "B", "category": "education", "amount": 2},
            ]
        },
    ],
)
def test_invalid_patches_are_rejected(session: SessionHandle, updates: dict[str, Any]) -> None:
    response = session.patch(updates)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert session.client.get(session.url(), headers=session.headers).json()["revision"] == 0


def test_patch_stale_revision(session: SessionHandle) -> None:
    session.patch({"support_years": 15})
    session.revision = 0
    response = session.patch({"support_years": 20})
    assert response.status_code == 409


def test_full_example_via_patch_is_complete(session: SessionHandle) -> None:
    body = session.patch(EXAMPLE_PATCH).json()
    assert body["next_question"] is None
    assessment = body["assessment"]
    assert assessment["status"] == "complete"
    assert assessment["additional_coverage_gap"] == 670_000
    assert [i["code"] for i in assessment["line_items"]] == [
        "ongoing_support",
        "one_time_expenses",
        "available_assets",
        "personal_coverage",
        "employer_coverage",
        "additional_gap",
    ]
    assert assessment["disclaimer"]
    assert "raw_gap" not in assessment


def test_saved_assessment_becomes_stale_after_edit(session: SessionHandle) -> None:
    session.patch(EXAMPLE_PATCH)
    saved = session.client.post(session.url("/assessments"), headers=session.headers)
    assert saved.status_code == 201
    assert saved.json()["is_current"] is True

    session.patch({"support_years": 20})
    latest = session.client.get(session.url("/assessments/latest"), headers=session.headers).json()
    assert latest["id"] == saved.json()["id"]
    assert latest["is_current"] is False
    assert "revision 1" in latest["stale_reason"]
    assert latest["additional_coverage_gap"] == 670_000  # saved results never change


def test_latest_assessment_404_when_none_saved(session: SessionHandle) -> None:
    response = session.client.get(session.url("/assessments/latest"), headers=session.headers)
    assert response.status_code == 404


def test_save_assessment_with_stale_expected_revision(session: SessionHandle) -> None:
    session.patch(EXAMPLE_PATCH)
    response = session.client.post(
        session.url("/assessments"), headers=session.headers, json={"expected_revision": 0}
    )
    assert response.status_code == 409


def test_more_personal_coverage_lowers_gap_by_exact_amount(session: SessionHandle) -> None:
    before = session.patch(EXAMPLE_PATCH).json()["assessment"]["additional_coverage_gap"]
    after = session.patch({"personal_coverage": 300_000}).json()["assessment"]
    assert before - after["additional_coverage_gap"] == 200_000


def test_scenarios_do_not_change_profile(session: SessionHandle) -> None:
    session.patch(EXAMPLE_PATCH)
    response = session.client.post(
        session.url("/scenarios"),
        headers=session.headers,
        json={
            "base_revision": session.revision,
            "scenarios": [
                {"name": "10 years", "overrides": {"support_years": 10}},
                {"name": "20 years", "overrides": {"support_years": 20}},
                {"name": "No employer cover", "overrides": {"exclude_employer_coverage": True}},
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    gaps = {s["name"]: s["result"]["additional_coverage_gap"] for s in body["scenarios"]}
    assert gaps == {"10 years": 370_000, "20 years": 970_000, "No employer cover": 820_000}
    assert body["scenarios"][0]["overrides"] == {"support_years": 10}
    assert body["base"]["additional_coverage_gap"] == 670_000
    assert body["range"] == {"low": 370_000, "high": 970_000}

    profile = session.client.get(session.url("/profile"), headers=session.headers).json()
    assert profile["profile"]["support_years"]["value"] == 15
    assert profile["revision"] == session.revision


def test_scenario_rejects_unknown_override_and_stale_base(session: SessionHandle) -> None:
    session.patch(EXAMPLE_PATCH)
    bad_key = session.client.post(
        session.url("/scenarios"),
        headers=session.headers,
        json={"base_revision": 1, "scenarios": [{"name": "x", "overrides": {"gap": 0}}]},
    )
    assert bad_key.status_code == 422
    stale = session.client.post(
        session.url("/scenarios"),
        headers=session.headers,
        json={"base_revision": 0, "scenarios": [{"name": "x", "overrides": {}}]},
    )
    assert stale.status_code == 409


def test_coverage_types_content(session: SessionHandle) -> None:
    body = session.client.get("/v1/content/coverage-types").json()
    assert {c["id"] for c in body["coverage_types"]} == {"term", "permanent"}
    assert body["review_status"] == "pending_compliance_review"
    assert body["resources"] == []
