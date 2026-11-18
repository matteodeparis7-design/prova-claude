from datetime import datetime, timedelta, timezone

import pytest

from promovo.modules.catalog import active_offers
from promovo.modules.content.service import (AIContent, ai_tells, generate_content, hero_offer, prices_ok,
                                             save_content)
from promovo.modules.content.writer import computed_prices, gather_facts
from promovo.modules.flyer.service import ingest_flyer
from promovo.modules.video.render import Renderer, RenderError, render_video, probe_duration
from promovo.modules.video.service import build_spec

from conftest import TODAY

NOW = datetime(2026, 11, 15, 10, 0, tzinfo=timezone.utc)


@pytest.fixture
def flyer(session, store, sample_pdf, tmp_settings):
    return ingest_flyer(session, store, sample_pdf, tmp_settings, None, today=TODAY)


def offer_named(flyer, prefix):
    return next(o for o in flyer.offers if o.name.startswith(prefix))


# ------------------------------------------------------------------ catalogo

def test_active_offers(session, store, flyer):
    assert len(active_offers(session, store.id, TODAY)) == 12
    assert active_offers(session, store.id, TODAY + timedelta(days=30)) == []


# ------------------------------------------------------------------ testi (redazione interna, senza IA)

def test_content_by_agents(session, store, flyer):
    pack = generate_content(store, flyer, None, today=TODAY)
    assert pack.source == "agents" and pack.warnings == []
    assert set(pack.texts) == {"instagram", "facebook", "reel", "plan"}
    assert "22 novembre" in pack.texts["instagram"]["body"]          # la fine delle offerte si dice sempre
    allowed = computed_prices(gather_facts(store, flyer, None, None, TODAY))
    for t in pack.texts.values():
        assert prices_ok(t["body"], allowed)
    pieces = save_content(session, store, flyer, pack)
    assert {p.kind for p in pieces} == {"instagram", "facebook", "reel", "plan"}
    assert all(not p.approved for p in pieces)
    assert save_content(session, store, flyer, pack) and len(flyer.store.flyers) == 1   # niente doppioni


@pytest.mark.parametrize("tone", ["familiare", "elegante", "giovane", "essenziale"])
def test_agent_texts_sound_human(session, store, flyer, tone):
    store.tone = tone
    pack = generate_content(store, flyer, None, today=TODAY)
    for kind, t in pack.texts.items():
        body = t["body"]
        assert ai_tells(t["title"] + "\n" + body) == [], (tone, kind)
        assert "—" not in body and body.count("!") <= 1
        if tone in ("elegante", "essenziale") and kind != "plan":
            assert not any(ord(ch) > 0x2600 for ch in body), (tone, kind)   # niente emoji
        if tone == "elegante" and kind != "plan":
            assert " ti " not in f" {body.lower()} " and "trovi" not in body.lower()     # si dà del voi
    first = pack.texts["instagram"]["body"].splitlines()[0]
    assert len(first) <= 100 and ("€" in first or "sotto l'euro" in first.lower())   # la prima riga ha un numero


def test_weekly_plan_uses_real_days(store, flyer):
    plan = generate_content(store, flyer, None, today=TODAY).texts["plan"]["body"]
    assert "13 novembre" in plan and "Reel 9:16" in plan and "22 novembre" in plan
    assert "WhatsApp" not in plan and "COSA FILMARE AL BANCO" in plan


# ------------------------------------------------------------------ testi con l'IA facoltativa

def test_ai_proposal_used_only_if_clean(session, store, flyer, fake_llm):
    fake_llm.on_parse("AIContent", lambda c: AIContent(
        strategia="La pasta della settimana.", instagram_caption="Spaghetti 500 g a € 0,79: € 0,50 in meno.",
        hashtags=["#offerte", "spesa"], facebook_post="Solo oggi tutto a € 0,10!"))   # prezzo inventato
    pack = generate_content(store, flyer, fake_llm, today=TODAY)
    assert pack.source == "ai"
    assert pack.texts["instagram"]["body"] == "Spaghetti 500 g a € 0,79: € 0,50 in meno."
    assert pack.texts["instagram"]["meta"]["hashtags"] == ["offerte", "spesa"]
    assert pack.texts["instagram"]["meta"]["strategy"] == "La pasta della settimana."
    assert "0,10" not in pack.texts["facebook"]["body"]                    # resta il testo degli agenti
    assert any("facebook" in w for w in pack.warnings)


def test_ai_cliches_rejected(store, flyer, fake_llm):
    fake_llm.on_parse("AIContent", lambda c: AIContent(
        instagram_caption="Un viaggio nel gusto: spaghetti a € 0,79!", hashtags=[], facebook_post="Scopri le offerte!"))
    pack = generate_content(store, flyer, fake_llm, today=TODAY)
    assert pack.source == "agents" and len(pack.warnings) == 2
    assert "viaggio" not in pack.texts["instagram"]["body"]


def test_ai_unavailable_keeps_agents(store, flyer, fake_llm):
    fake_llm.unavailable = True
    pack = generate_content(store, flyer, fake_llm, today=TODAY)
    assert pack.source == "agents" and pack.warnings and pack.texts["instagram"]["body"]


def test_hero_prefers_food(store, flyer):
    assert hero_offer(list(flyer.offers)).category not in ("igiene casa", "cura persona")


# ------------------------------------------------------------------ video

def test_video_renders_both_formats(store, flyer, tmp_path):
    for fmt in ("landscape", "portrait"):
        spec = build_spec(store, flyer, fmt, scale=0.25, max_offers=2)
        spec.intro_seconds = spec.outro_seconds = 1.0
        spec.offer_seconds = 1.0
        out = render_video(spec, tmp_path / f"{fmt}.mp4", preset="ultrafast")
        assert out.exists() and out.stat().st_size > 1000
        assert abs(probe_duration(out) - 4.0) < 0.2
        r = Renderer(spec)
        assert r.W % 2 == 0 and r.H % 2 == 0
        assert (r.H > r.W) == (fmt == "portrait")
    assert not list(tmp_path.glob("*.part.mp4"))


def test_video_portrait_uses_featured(store, flyer):
    spec = build_spec(store, flyer, "portrait")
    assert len(spec.offers) == 6
    featured = {o.name for o in flyer.offers if o.is_featured}
    assert {o.name for o in spec.offers} == featured
    assert len(build_spec(store, flyer, "landscape").offers) == 12


def test_video_errors(store, flyer, tmp_path):
    spec = build_spec(store, flyer, "landscape")
    spec.offers = []
    with pytest.raises(RenderError):
        render_video(spec, tmp_path / "x.mp4")
    with pytest.raises(RenderError):
        build_spec(store, flyer, "cinema")


def test_video_long_texts_fit(store, flyer):
    spec = build_spec(store, flyer, "portrait", scale=0.5, max_offers=1)
    spec.offers[0].name = "Nome di prodotto lunghissimo " * 8
    spec.offers[0].conditions = "Con carta fedeltà, massimo 3 pezzi per cliente, fino a esaurimento"
    spec.store_name = "Supermercato con un nome davvero molto molto lungo"
    r = Renderer(spec)
    for t in (0.5, 4.5, r.duration - 0.1):
        img = r.frame_at(t)
        assert img.size == (r.W, r.H)
