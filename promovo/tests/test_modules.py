from datetime import datetime, timedelta, timezone

import pytest

from promovo.models import Customer, Order, OrderStatus
from promovo.modules.analytics.service import SalesImportError, flyer_performance, import_sales_csv
from promovo.modules.assistant.agent import OrderError, chat, create_pickup_order, normalize_phone
from promovo.modules.catalog import active_offers, search_offers
from promovo.modules.content.service import AIContent, generate_content, prices_ok, save_content
from promovo.modules.flyer.service import ingest_flyer
from promovo.modules.loyalty.service import build_campaign, handle_inbound, set_consent
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

def test_active_offers_and_search(session, store, flyer):
    offers = active_offers(session, store.id, TODAY)
    assert len(offers) == 12
    assert active_offers(session, store.id, TODAY + timedelta(days=30)) == []
    assert [o.name for o in search_offers(offers, "pollo")] == ["Petto di pollo a fette"]
    assert search_offers(offers, "caffe")[0].name == "Caffè macinato"
    assert search_offers(offers, "", "bevande")[0].name == "Acqua naturale"
    assert search_offers(offers, "astronave") == []


# ------------------------------------------------------------------ contenuti

def test_content_template(store, flyer):
    pack = generate_content(store, flyer, None)
    assert pack.source == "template"
    assert set(pack.texts) == {"instagram", "facebook", "whatsapp", "newsletter", "plan"}
    assert "dal 13 al 22 novembre" in pack.texts["instagram"]["body"]
    assert "STOP" in pack.texts["whatsapp"]["body"]
    allowed = {o.price_cents for o in flyer.offers} | {o.old_price_cents for o in flyer.offers if o.old_price_cents}
    allowed |= {o.old_price_cents - o.price_cents for o in flyer.offers if o.old_price_cents}   # risparmi calcolati
    allowed |= {800, 2000, 900, 1300}                      # orari del negozio (8.00-20.00, 9.00-13.00)
    for t in pack.texts.values():
        assert prices_ok(t["body"], allowed)


def test_content_ai_with_price_guard(session, store, flyer, fake_llm):
    fake_llm.on_parse("AIContent", lambda c: AIContent(
        instagram_caption="Spaghetti a € 0,79! 🍝", hashtags=["#offerte", "spesa"],
        facebook_post="Solo oggi tutto a € 0,10!",  # prezzo inventato: va scartato
        whatsapp_message="Spaghetti a € 0,79 invece di € 1,29",  # manca STOP: va aggiunto
        newsletter_subject="Offerte", newsletter_body="Olio a € 6,99."))
    pack = generate_content(store, flyer, fake_llm)
    assert pack.source == "ai"
    assert pack.texts["instagram"]["body"] == "Spaghetti a € 0,79! 🍝"
    assert pack.texts["instagram"]["meta"]["hashtags"] == ["offerte", "spesa"]
    assert "0,10" not in pack.texts["facebook"]["body"]
    assert any("facebook" in w for w in pack.warnings)
    assert pack.texts["whatsapp"]["body"].endswith("Rispondi STOP per non ricevere più messaggi.")
    pieces = save_content(session, store, flyer, pack)
    assert {p.kind for p in pieces} == {"instagram", "facebook", "whatsapp", "newsletter", "plan"}
    assert all(not p.approved for p in pieces)


def test_content_ai_unavailable(store, flyer, fake_llm):
    fake_llm.unavailable = True
    pack = generate_content(store, flyer, fake_llm)
    assert pack.source == "template" and pack.warnings


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


# ------------------------------------------------------------------ ordini e assistente

@pytest.mark.parametrize("raw,norm", [("333 1234567", "+393331234567"), ("+39 333 1234567", "+393331234567"),
                                      ("0039 06 123456", "+3906123456"), ("06-1234567", "+39061234567")])
def test_normalize_phone(raw, norm):
    assert normalize_phone(raw) == norm


@pytest.mark.parametrize("raw", ["", "abc", "12", "+39 333 123456789012345678"])
def test_normalize_phone_invalid(raw):
    with pytest.raises(OrderError):
        normalize_phone(raw)


def test_create_order_and_validations(session, store, flyer):
    pasta, olio = offer_named(flyer, "Spaghetti"), offer_named(flyer, "Olio")
    pickup = "2026-11-16T18:30"
    order = create_pickup_order(session, store, name="Mario Rossi", phone="333 1234567",
                                items=[{"offerta_id": pasta.id, "quantita": 2}, {"offerta_id": olio.id, "quantita": 1},
                                       {"offerta_id": pasta.id, "quantita": 1}],
                                pickup_iso=pickup, now=NOW)
    assert order.total_cents == 3 * 79 + 699
    assert [(i.name, i.quantity) for i in order.items] == [("Spaghetti di grano duro", 3),
                                                            ("Olio extravergine di oliva", 1)]
    assert order.customer.phone == "+393331234567"
    # Il cliente non viene duplicato.
    create_pickup_order(session, store, name="Mario Rossi", phone="+39 333 1234567",
                        items=[{"offerta_id": olio.id, "quantita": 1}], pickup_iso=pickup, now=NOW)
    assert session.query(Customer).count() == 1

    bad = [
        (dict(items=[]), "vuoto"),
        (dict(items=[{"offerta_id": 99999, "quantita": 1}]), "non esiste"),
        (dict(items=[{"offerta_id": pasta.id, "quantita": 0}]), "Quantità"),
        (dict(items=[{"offerta_id": pasta.id, "quantita": 30}, {"offerta_id": pasta.id, "quantita": 30}]), "troppo alta"),
        (dict(pickup_iso="2026-11-15T10:30"), "almeno tra un'ora"),
        (dict(pickup_iso="2026-12-20T10:00"), "7 giorni"),
        (dict(pickup_iso="domani"), "non valido"),
        (dict(name="x"), "nome"),
        (dict(phone="abc"), "telefono"),
        (dict(items=[{"quantita": 1}]), "offerta_id"),
    ]
    for override, msg in bad:
        args = dict(name="Mario", phone="3331234567", items=[{"offerta_id": pasta.id, "quantita": 1}],
                    pickup_iso=pickup)
        args.update(override)
        with pytest.raises(OrderError, match=msg):
            create_pickup_order(session, store, now=NOW, **args)
    store.pickup_enabled = False
    with pytest.raises(OrderError, match="non accetta"):
        create_pickup_order(session, store, name="Mario", phone="3331234567",
                            items=[{"offerta_id": pasta.id, "quantita": 1}], pickup_iso=pickup, now=NOW)


def test_chat_flow_with_tools(session, store, flyer, fake_llm):
    pollo = offer_named(flyer, "Petto di pollo")
    fake_llm.scripts.append([
        [("cerca_offerte", {"testo": "pollo", "categoria": ""}), ("info_negozio", {})],
        "Sì! Petto di pollo a fette a € 7,99 al kg.",
    ])
    reply, conv = chat(session, store, fake_llm, "Avete il pollo in offerta?", now=NOW)
    assert "7,99" in reply
    results = conv.history[2]["content"]
    assert results[0]["tool_use_id"].startswith("toolu_")
    assert "Petto di pollo a fette" in results[0]["content"]
    assert "Via Roma 1" in results[1]["content"]

    # Secondo turno nella stessa conversazione: ordine + uno strumento con errore.
    pickup = (NOW + timedelta(days=1)).astimezone().strftime("%Y-%m-%dT18:00")
    fake_llm.scripts.append([
        [("crea_ordine_ritiro", {"nome": "Anna Bianchi", "telefono": "3471112223",
                                 "articoli": [{"offerta_id": pollo.id, "quantita": 2}],
                                 "ritiro": pickup, "note": ""}),
         ("stato_ordine", {"ordine_id": 12345, "telefono": "3471112223"})],
        "Ordine creato!",
    ])
    reply2, conv2 = chat(session, store, fake_llm, "Sì, confermo l'ordine", conversation=conv, now=NOW)
    assert conv2.id == conv.id
    assert reply2 == "Ordine creato!"
    order = session.query(Order).one()
    assert order.total_cents == 2 * pollo.price_cents and order.status == OrderStatus.new
    last_results = conv2.history[-2]["content"]
    assert last_results[1]["is_error"] is True
    # La cronologia contiene il primo turno.
    assert conv2.history[0]["content"] == "Avete il pollo in offerta?"


def test_chat_rejects_empty(session, store, fake_llm):
    with pytest.raises(ValueError):
        chat(session, store, fake_llm, "   ")


# ------------------------------------------------------------------ vendite

SALES = """data;prodotto;quantita;incasso
06/11/2026;SPAGHETTI DI GRANO DURO 500G;10;12,90
10/11/2026;SPAGHETTI DI GRANO DURO 500G;10;12,90
14/11/2026;SPAGHETTI DI GRANO DURO 500G;30;23,70
20/11/2026;SPAGHETTI DI GRANO DURO 500G;20;15,80
07/11/2026;MELE GOLDEN;5,5;8,20
15/11/2026;MELE GOLDEN;5;7,45
riga;rotta
16/11/2026;PRODOTTO SCONOSCIUTO;1;1,00
"""


def test_sales_import_and_performance(session, store, flyer):
    rep = import_sales_csv(session, store, SALES.encode("utf-8"))
    assert rep.imported == 7 and rep.skipped == 1
    assert rep.first_day.isoformat() == "2026-11-06" and rep.last_day.isoformat() == "2026-11-20"
    # Reimportare lo stesso file non raddoppia i dati.
    import_sales_csv(session, store, SALES.encode("utf-8"))
    perf = flyer_performance(session, flyer)
    by = {r["name"]: r for r in perf["offers"]}
    pasta = by["Spaghetti di grano duro"]
    assert pasta["qty_during"] == 50 and pasta["qty_before"] == 20
    assert pasta["uplift_percent"] == 150.0
    assert pasta["revenue_during_cents"] == 2370 + 1580
    mele = by["Mele Golden"]
    assert mele["qty_before"] == 5.5 and mele["qty_during"] == 5
    assert perf["summary"]["offers_measured"] == 2
    assert any("Spaghetti" in s for s in perf["suggestions"])
    assert any("Mele Golden" in s for s in perf["suggestions"])


@pytest.mark.parametrize("data,msg", [
    (b"", "vuoto"),
    (b"data,prodotto\n2026-11-01,x\n", "Colonne mancanti"),
    (b"data,prodotto,quantita,incasso\nboh,x,1,1\n", "Nessuna riga valida"),
])
def test_sales_import_errors(session, store, data, msg):
    with pytest.raises(SalesImportError, match=msg):
        import_sales_csv(session, store, data)


def test_sales_comma_csv_and_latin1(session, store):
    data = "Data,Prodotto,Quantità,Incasso\n2026-11-14,Caffè macinato,2,4.98\n".encode("latin-1")
    rep = import_sales_csv(session, store, data)
    assert rep.imported == 1


def test_performance_needs_dates(session, store, flyer):
    flyer.valid_from = None
    with pytest.raises(SalesImportError, match="date"):
        flyer_performance(session, flyer)


# ------------------------------------------------------------------ fedeltà

def test_campaign_only_with_consent_and_stop(session, store, flyer):
    a = Customer(store_id=store.id, name="Anna Verdi", phone="+393330000001", preferred_categories=["pesce"])
    b = Customer(store_id=store.id, name="Bruno", phone="+393330000002")
    session.add_all([a, b])
    session.flush()
    set_consent(session, a, True)
    msgs = build_campaign(session, store, flyer)
    assert len(msgs) == 1
    assert msgs[0].meta["customer_id"] == a.id
    assert msgs[0].body.startswith("Ciao Anna!")
    assert "Salmone affumicato" in msgs[0].body  # la sua categoria preferita viene prima
    assert "STOP" in msgs[0].body
    assert handle_inbound(session, store, "333 0000001", "Stop!")
    assert a.marketing_consent is False and a.consent_at is None
    assert build_campaign(session, store, flyer) == []
    assert not handle_inbound(session, store, "3330000001", "Ciao, a che ora chiudete?")


# ------------------------------------------------------------------ copywriter: qualità dei testi

from promovo.modules.content.service import AIEdited, ai_tells, hero_offer  # noqa: E402


@pytest.mark.parametrize("tone", ["familiare", "elegante", "giovane", "essenziale"])
def test_template_texts_sound_human(session, store, flyer, tone):
    store.tone = tone
    pack = generate_content(store, flyer, None)
    for kind, t in pack.texts.items():
        assert ai_tells(t["title"] + "\n" + t["body"]) == [], (tone, kind)
        assert "—" not in t["body"]
        if tone in ("elegante", "essenziale") and kind != "plan":
            assert not any(ord(ch) > 0x2600 for ch in t["body"]), (tone, kind)   # niente emoji
    hero = hero_offer([o for o in flyer.offers])
    first = pack.texts["instagram"]["body"].splitlines()[0]
    assert hero.name.lower() in first.lower()          # la prima riga nomina il protagonista
    assert len(pack.texts["whatsapp"]["body"]) <= 700
    assert pack.texts["newsletter"]["title"] and len(pack.texts["newsletter"]["title"]) <= 45


def test_weekly_plan_uses_real_days(store, flyer):
    plan = generate_content(store, flyer, None).texts["plan"]["body"]
    assert "13 novembre" in plan and "Reel 9:16" in plan and "WhatsApp" in plan
    assert "22 novembre" in plan                       # l'ultimo giorno di offerte


def test_ai_editor_pass_rewrites_and_flags(store, flyer, fake_llm):
    draft = dict(strategia="Protagonista la pasta.", instagram_caption="Offerte imperdibili! Scopri il volantino",
                 hashtags=["offerte"], facebook_post="Spaghetti a € 0,79.", whatsapp_message="Spaghetti a € 0,79",
                 newsletter_subject="Spaghetti a € 0,79", newsletter_body="Spaghetti a € 0,79.")
    fake_llm.on_parse("AIContent", lambda c: AIContent(**draft))
    seen = {}

    def editor(content):
        seen["text"] = content[0]["text"]
        return AIEdited(difetti=["«imperdibili» e «scopri» sono frasi fatte"],
                        **{**draft, "instagram_caption": "Spaghetti 500 g a € 0,79: € 0,50 in meno."})
    fake_llm.on_parse("AIEdited", editor)
    pack = generate_content(store, flyer, fake_llm)
    assert pack.texts["instagram"]["body"] == "Spaghetti 500 g a € 0,79: € 0,50 in meno."   # il risparmio è ammesso
    assert pack.texts["instagram"]["meta"]["strategy"] == "Protagonista la pasta."
    assert "BOZZE DEL COPYWRITER" in seen["text"] and "risparmio € 0,50" in seen["text"]
    assert ("parse", "AIEdited") in fake_llm.calls


def test_ai_text_with_cliches_is_flagged(store, flyer, fake_llm):
    fake_llm.on_parse("AIContent", lambda c: AIContent(
        instagram_caption="Un viaggio nel gusto: spaghetti a € 0,79!", hashtags=[], facebook_post="ok € 0,79",
        whatsapp_message="€ 0,79", newsletter_subject="Pasta", newsletter_body="€ 0,79"))
    pack = generate_content(store, flyer, fake_llm)          # nessun caporedattore: resta la bozza
    assert any("instagram" in w and "viaggio" in w for w in pack.warnings)
