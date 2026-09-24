"""TASK 31/32: browser navigation and persisted feedback in one real stack."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from playwright.sync_api import expect
from sqlalchemy import select

from app.models import (
    Favorite,
    InitialTestAssignment,
    Interaction,
    PreferenceEvent,
    TriggerSample,
    User,
    UserLanguagePreference,
    UserPreference,
)
from app.models import (
    TestResponse as SampleResponse,
)
from app.sessions import COOKIE_NAME, sign_identity


def at(flow, path):
    expect(flow.page).to_have_url(flow.origin + path)


def button(page, name):
    return page.get_by_role("button", name=name, exact=True)


def nav(flow, name, path):
    flow.page.get_by_role("navigation", name="Main navigation").get_by_role(
        "link", name=name, exact=True,
    ).click()
    at(flow, path)


def evidence(flow):
    flow.db.expire_all()
    preferences = [
        (row.trigger_id, row.score, row.evidence_count, row.last_evidence_source)
        for row in flow.db.scalars(select(UserPreference).order_by(
            UserPreference.trigger_id,
        ))
    ]
    events = [
        (row.id, row.trigger_id, row.source, row.observation)
        for row in flow.db.scalars(select(PreferenceEvent).order_by(
            PreferenceEvent.id,
        ))
    ]
    return preferences, events


def preference(flow, key):
    flow.db.expire_all()
    return flow.db.scalar(select(UserPreference).where(
        UserPreference.trigger_id == flow.features[key],
    ))


def card(flow, key):
    return flow.page.get_by_role("article", name=f"Fixture {key}", exact=True)


def sentiment(flow, key, action):
    item = card(flow, key)
    button(item, action).click()
    expect(button(item, action)).to_have_attribute("aria-pressed", "true")
    expect(item.get_by_role("status")).to_contain_text("taste has been updated")


@pytest.mark.parametrize(
    "extended,voice,language,extras",
    [
        (False, "No Talking", None, False),
        (True, "Talking", "English", True),
        (False, "Both", "No preference", True),
    ],
)
def test_fresh_session_to_first_taste_and_home(
    flow, extended, voice, language, extras,
):
    page = flow.page
    assert flow.context.cookies() == []
    assert flow.db.scalar(select(User)) is None
    page.goto(flow.origin)
    at(flow, "/test")
    expect(page.get_by_title("Sound sample 1")).to_be_visible()
    cookie = next(c for c in flow.context.cookies() if c["name"] == COOKIE_NAME)
    assert cookie["httpOnly"] and cookie["sameSite"] == "Lax"
    answers = ["Like", "Neutral", "Dislike", "Skip", "Like", "Neutral"]
    for index, answer in enumerate(answers, start=1):
        expect(page.get_by_title(f"Sound sample {index}")).to_be_visible()
        button(page, answer).click()
        expect(button(page, "Next")).to_be_visible()
        if index == 1:
            # Resume without any test-side cookie restoration or API state setup.
            page.reload()
            expect(page.get_by_title("Sound sample 2")).to_be_visible()
            stored = flow.db.scalar(select(SampleResponse))
            assert stored.response == "like"
        else:
            button(page, "Next").click()
    expect(page.get_by_role(
        "heading", name="Want to try 2 more sounds?",
    )).to_be_visible()
    if extended:
        button(page, "Try 2 more").click()
        for index in (7, 8):
            expect(page.get_by_title(f"Sound sample {index}")).to_be_visible()
            button(page, "Skip").click()
            button(page, "Next" if index == 7 else "Continue").click()
    else:
        button(page, "Continue").click()
    at(flow, "/onboarding/voice")
    page.reload()
    expect(page.get_by_role("radio", name=voice, exact=True)).to_be_visible()
    responses = list(flow.db.scalars(select(SampleResponse).order_by(
        SampleResponse.id,
    )))
    expected = [answer.lower() for answer in answers]
    if extended:
        expected += ["skip"] * 2
    assert [row.response for row in responses] == expected
    assignments = list(flow.db.scalars(select(InitialTestAssignment)))
    assert len(assignments) == (8 if extended else 6)
    page.get_by_role("radio", name=voice, exact=True).check()
    button(page, "Continue").click()
    if language:
        at(flow, "/onboarding/languages")
        page.goto(flow.origin)
        at(flow, "/onboarding/languages")
        page.get_by_role("checkbox", name=language, exact=True).check()
        button(page, "Continue").click()
    at(flow, "/onboarding/extra-preferences")
    page.reload()
    expect(page.get_by_role("checkbox", name="roleplay", exact=True)).to_be_visible()
    expect(page.get_by_role(
        "checkbox", name="hand_movements", exact=True,
    )).to_be_visible()
    expect(page.locator("iframe")).to_have_count(0)
    presented = {
        flow.db.get(TriggerSample, row.sample_id).primary_trigger_id
        for row in assignments
    }
    for key, feature_id in flow.features.items():
        if feature_id not in presented:
            continue
        expect(page.get_by_role("checkbox", name=key, exact=True)).to_have_count(0)
    unpresented_sound = next(
        key for key, feature_id in flow.features.items()
        if feature_id not in presented and key not in {"roleplay", "hand_movements"}
    )
    if extras:
        page.get_by_role("checkbox", name="roleplay", exact=True).check()
        page.get_by_role("checkbox", name=unpresented_sound, exact=True).check()
        button(page, "Continue").click()
    else:
        button(page, "Skip").click()
    at(flow, "/my-taste?first=1")
    expect(page.get_by_role(
        "heading", name="Your current taste", exact=True,
    )).to_be_visible()
    expect(page.get_by_role("heading", name="Favorite Sounds")).to_be_visible()
    flow.db.expire_all()
    user = flow.db.scalar(select(User))
    assert user.onboarding_completed and user.initial_test_completed_at
    modes = {"Talking": "talking", "Both": "both", "No Talking": "no_talking"}
    assert user.voice_mode == modes[voice]
    assert user.language_no_preference == (language == "No preference")
    assert list(flow.db.scalars(select(UserLanguagePreference.language))) == (
        ["en"] if language == "English" else []
    )
    assert preference(flow, "tapping").score == Decimal("0.4500")
    assert preference(flow, "scratching").score == 0
    assert preference(flow, "mic_brushing").score == Decimal("-0.4500")
    assert preference(flow, "ear_cleaning") is None  # Skip is not dislike.
    assert preference(flow, "hand_movements") is None  # Unselected is unknown.
    assert bool(preference(flow, "roleplay")) == extras
    if extras:
        assert preference(flow, unpresented_sound).score == Decimal("0.3500")
        assert preference(flow, unpresented_sound).evidence_count == 1
    page.get_by_role("link", name="See my recommendations", exact=True).click()
    at(flow, "/home")
    expect(page.get_by_role("heading", name="For You")).to_be_visible()
    before = evidence(flow)
    page.goto(flow.origin)
    at(flow, "/home")
    expect(card(flow, "tapping")).to_be_visible()
    assert evidence(flow) == before
    current_cookie = next(
        c for c in flow.context.cookies() if c["name"] == COOKIE_NAME
    )
    assert current_cookie["value"] == cookie["value"]
    assert len(list(flow.db.scalars(select(User)))) == 1
    if not language:
        assert not any("/languages" in path for _, path, _ in flow.api_calls)
    assert any(path.startswith("/embed/") for path in flow.youtube)


def test_returning_retention_loop(flow):
    now = datetime.now(timezone.utc)
    user = User(
        created_at=now, taxonomy_version="2.0", onboarding_completed=True,
        initial_test_completed_at=now, voice_mode="no_talking",
    )
    flow.db.add(user)
    flow.db.flush()
    flow.db.add(UserPreference(
        user_id=user.id, trigger_id=flow.features["tapping"],
        score=Decimal("0.45"), evidence_count=1,
        last_evidence_source="test", updated_at=now,
    ))
    flow.db.add(PreferenceEvent(
        user_id=user.id, trigger_id=flow.features["tapping"],
        source="test", observation=1, created_at=now,
    ))
    flow.db.commit()
    flow.context.add_cookies([{
        "name": COOKIE_NAME,
        "value": sign_identity(user.id, b"e2e-only-session-secret-at-least-32-bytes"),
        "url": flow.origin, "httpOnly": True, "sameSite": "Lax",
    }])
    page = flow.page
    page.goto(flow.origin)
    at(flow, "/home")
    item = card(flow, "tapping")
    expect(item).to_be_visible()
    before = evidence(flow)
    button(item, "Play").click()
    expect(item.get_by_title("Play Fixture tapping")).to_be_visible()
    assert evidence(flow) == before
    assert flow.db.scalar(select(Interaction).where(Interaction.type == "play"))
    sentiment(flow, "tapping", "Like")
    row = preference(flow, "tapping")
    assert (row.score, row.evidence_count) == (Decimal("0.5600"), 2)
    sentiment(flow, "tapping", "Dislike")
    row = preference(flow, "tapping")
    assert (row.score, row.evidence_count) == (Decimal("0.2480"), 3)
    assert [event[2] for event in evidence(flow)[1]] == [
        "test", "video_like", "video_dislike",
    ]
    before = evidence(flow)
    button(item, "Save").click()
    expect(button(item, "Remove saved")).to_be_visible()
    assert flow.db.get(Favorite, (user.id, flow.videos["tapping"]))
    button(item, "Remove saved").click()
    expect(button(item, "Save")).to_be_visible()
    assert flow.db.get(Favorite, (user.id, flow.videos["tapping"])) is None
    button(item, "Save").click()
    expect(button(item, "Remove saved")).to_be_visible()
    assert evidence(flow) == before
    button(item, "Skip").click()
    expect(item).to_have_count(0)
    button(card(flow, "tapping sibling 1"), "Skip").click()
    expect(card(flow, "tapping sibling 1")).to_have_count(0)
    page.reload()
    expect(card(flow, "tapping sibling 2")).to_be_visible()
    expect(card(flow, "tapping sibling 1")).to_have_count(0)
    expect(item).to_have_count(0)
    assert evidence(flow) == before
    nav(flow, "My Taste", "/my-taste")
    expect(page.get_by_role("heading", name="Neutral / Disliked")).to_be_visible()
    expect(page.get_by_role("heading", name="Recently discovered")).to_have_count(0)
    nav(flow, "Discover", "/discover")
    sentiment(flow, "hand_movements", "Like")
    row = preference(flow, "hand_movements")
    assert (row.score, row.evidence_count, row.last_evidence_source) == (
        Decimal("0.2000"), 1, "discover_like",
    )
    nav(flow, "My Taste", "/my-taste")
    recent = page.locator("section").filter(has=page.get_by_role(
        "heading", name="Recently discovered",
    ))
    expect(recent.get_by_text("hand_movements", exact=True)).to_be_visible()
    expect(recent.locator(".state-label")).to_contain_text("Neutral")
    expect(recent.get_by_text("tapping", exact=True)).to_have_count(0)
    nav(flow, "Search", "/search")
    expect(card(flow, "roleplay")).to_be_visible()
    before = evidence(flow)
    page.get_by_label("Search videos or channels").fill("roleplay")
    button(page, "Search").click()
    expect(card(flow, "roleplay")).to_be_visible()
    expect(card(flow, "paper_crinkling")).to_have_count(0)
    page.reload()
    expect(card(flow, "paper_crinkling")).to_be_visible()
    page.locator("summary").click()
    page.get_by_role("checkbox", name="roleplay", exact=True).check()
    button(page, "Search").click()
    expect(card(flow, "roleplay")).to_be_visible()
    expect(card(flow, "paper_crinkling")).to_have_count(0)
    button(page, "Clear All").click()
    expect(card(flow, "paper_crinkling")).to_be_visible()
    assert evidence(flow) == before
    sentiment(flow, "roleplay", "Like")
    assert preference(flow, "roleplay").last_evidence_source == "video_like"
    before = evidence(flow)
    button(card(flow, "paper_crinkling"), "Save").click()
    expect(button(card(flow, "paper_crinkling"), "Remove saved")).to_be_visible()
    assert evidence(flow) == before
    nav(flow, "Saved", "/favorites")
    page.reload()
    expect(card(flow, "paper_crinkling")).to_be_visible()
    expect(button(card(flow, "tapping"), "Remove saved")).to_be_visible()
    sentiment(flow, "paper_crinkling", "Like")
    assert preference(flow, "paper_crinkling").last_evidence_source == "video_like"
    before = evidence(flow)
    button(card(flow, "tapping"), "Remove saved").click()
    expect(card(flow, "tapping")).to_have_count(0)
    page.reload()
    expect(card(flow, "paper_crinkling")).to_be_visible()
    expect(card(flow, "tapping")).to_have_count(0)
    assert evidence(flow) == before
    nav(flow, "My Taste", "/my-taste")
    expect(recent.get_by_text("hand_movements", exact=True)).to_be_visible()
    expect(recent.locator("li")).to_have_count(1)
    page.goto(flow.origin)
    at(flow, "/home")
    expect(card(flow, "tapping sibling 2")).to_be_visible()
    assert len(list(flow.db.scalars(select(User)))) == 1
    assert flow.db.get(User, user.id).onboarding_completed
    assert evidence(flow) == before
    assert "/iframe_api" in flow.youtube
