"""Montaggio del video tutorial: schede, didascalie, dissolvenze. Uscita MP4 1280x720 30fps."""
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

D = Path(sys.argv[1])
FONTS = Path("/home/user/prova-claude/promovo/promovo/assets/fonts")
W, H, FPS = 1280, 720, 30
INK, PAPER, BRAND, GOLD, MUTED = (20, 27, 45), (246, 244, 239), (229, 72, 47), (245, 184, 61), (200, 207, 224)
OUT = D / "parts"
OUT.mkdir(exist_ok=True)


def font(size, bold=False):
    return ImageFont.truetype(str(FONTS / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")), size)


def wrap(text, f, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if f.getlength(t) <= width:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def logo(d, x, y, size=44):
    d.rounded_rectangle((x, y, x + size, y + size), radius=size // 4, fill=BRAND)
    f = font(int(size * 0.62), True)
    d.text((x + size / 2, y + size / 2), "P", font=f, fill="white", anchor="mm")
    d.text((x + size + 14, y + size / 2), "PROMOVO", font=font(int(size * 0.55), True), fill="white", anchor="lm")


def card_bg():
    img = Image.new("RGB", (W, H), INK)
    glow = Image.new("RGB", (W, H), INK)
    gd = ImageDraw.Draw(glow)
    for r in range(520, 0, -8):
        a = int(70 * (1 - r / 520))
        gd.ellipse((-260 - r, -260 - r, 260 + r, 260 + r), fill=(INK[0] + a * 2, INK[1] + a // 2, INK[2] + a // 4))
    return Image.blend(img, glow, 0.9)


def card_title(path):
    img = card_bg()
    d = ImageDraw.Draw(img)
    logo(d, 90, 80, 56)
    y = 250
    for line in ["Il volantino del tuo negozio", "diventa comunicazione digitale."]:
        d.text((90, y), line, font=font(54, True), fill="white")
        y += 68
    d.text((90, y + 6), "Da solo.", font=font(54, True), fill=GOLD)
    d.text((90, y + 110), "Video tutorial · come funziona e come si usa", font=font(26), fill=MUTED)
    img.save(path)


def card_list(path, title, items, eyebrow, numbered=False, footer=None):
    img = card_bg()
    d = ImageDraw.Draw(img)
    logo(d, 90, 60, 40)
    d.text((90, 160), eyebrow.upper(), font=font(22, True), fill=GOLD)
    tl = wrap(title, font(44, True), W - 180)
    for k, ln in enumerate(tl):
        d.text((90, 196 + k * 54), ln, font=font(44, True), fill="white")
    y = 196 + 54 * len(tl) + 50
    for i, it in enumerate(items, 1):
        if numbered:
            d.ellipse((90, y - 4, 136, y + 42), fill=BRAND)
            d.text((113, y + 19), str(i), font=font(24, True), fill="white", anchor="mm")
        else:
            d.rounded_rectangle((96, y + 10, 114, y + 28), radius=5, fill=BRAND)
        lines = wrap(it, font(28), W - 300)
        for j, ln in enumerate(lines):
            d.text((160, y + j * 37), ln, font=font(28), fill="white")
        y += 37 * len(lines) + 26
    if footer:
        assert y < H - 70, f"testo troppo lungo nella scheda {title}"
        d.text((90, H - 56), footer, font=font(24), fill=MUTED)
    img.save(path)


def caption(path, step, title, text):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    lines = wrap(text, font(25), W - 260)
    bh = 92 + 34 * len(lines)
    y0 = H - bh - 24
    d.rounded_rectangle((40, y0, W - 40, H - 24), radius=22, fill=(20, 27, 45, 236))
    x = 70
    if step:
        d.rounded_rectangle((70, y0 + 20, 112, y0 + 62), radius=12, fill=BRAND)
        d.text((91, y0 + 41), str(step), font=font(24, True), fill="white", anchor="mm")
        x = 130
    d.text((x, y0 + 22), title, font=font(30, True), fill="white")
    for i, ln in enumerate(lines):
        d.text((70, y0 + 72 + i * 34), ln, font=font(25), fill=(222, 228, 240))
    img.save(path)


def duration(path):
    out = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path)], capture_output=True, text=True).stderr
    h, m, s = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out).groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


ENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS),
       "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2"]


def still(png, seconds, out):
    fade = f"fade=t=in:st=0:d=0.5,fade=t=out:st={seconds - 0.5}:d=0.5"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-t", str(seconds), "-i", str(png),
                    "-f", "lavfi", "-t", str(seconds), "-i", "anullsrc=r=48000:cl=stereo",
                    "-vf", f"scale={W}:{H},{fade}", *ENC, "-shortest", str(out)], check=True)


def clip(webm, cap_png, out, trim_start=0.7, speed=1.0):
    total = duration(webm)
    length = (total - trim_start) / speed
    vf = (f"[0:v]trim=start={trim_start},setpts=(PTS-STARTPTS)/{speed},scale={W}:{H},fps={FPS}[v];"
          f"[1:v]format=rgba,fade=t=in:st=0.3:d=0.6:alpha=1[c];"
          f"[v][c]overlay=0:0,fade=t=in:st=0:d=0.4,fade=t=out:st={length - 0.5}:d=0.5[o]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(webm), "-loop", "1", "-t", str(length),
                    "-i", str(cap_png), "-f", "lavfi", "-t", str(length), "-i", "anullsrc=r=48000:cl=stereo",
                    "-filter_complex", vf, "-map", "[o]", "-map", "2:a", *ENC, "-t", str(length), str(out)],
                   check=True)


C = D / "cards"
C.mkdir(exist_ok=True)
card_title(C / "00_titolo.png")
card_list(C / "01_problema.png", "Il volantino di carta da solo non basta più", [
    "Si stampa ogni settimana, costa e finisce nella spazzatura.",
    "I clienti cercano le offerte sul telefono, su Instagram e WhatsApp.",
    "Fare video e post ogni settimana richiede tempo, competenze o un'agenzia.",
], "Il problema")
card_list(C / "02_soluzione.png", "Un volantino in ingresso, una settimana di comunicazione", [
    "Carichi il volantino del negozio (PDF o foto).",
    "Gli agenti IA leggono ogni offerta e controllano ogni prezzo.",
    "Ricevi video, post e messaggi pronti: tu controlli e approvi.",
], "Come funziona", numbered=True)
card_list(C / "99_fine.png", "Ogni settimana, in pochi minuti", [
    "Video per gli schermi del negozio e Reel per i social.",
    "Testi per Instagram, Facebook, WhatsApp e newsletter.",
    "Prezzi controllati uno per uno, nessuna pubblicazione senza il tuo ok.",
    "In arrivo: assistente clienti su WhatsApp, ordini da ritirare, ricette e analisi delle vendite.",
], "Cosa ottieni", footer="Promovo · Prova gratuita per i primi negozi pilota")

STEPS = [
    ("s1_accesso", 1, "Accedi a Promovo", "Dalla panoramica vedi subito volantini, offerte attive, contenuti da approvare, ordini e clienti."),
    ("s2_carica", 2, "Carica il volantino", "Trascini il PDF o la foto del volantino. Gli agenti leggono ogni offerta: prodotto, formato, prezzo, sconto e foto, e controllano ogni prezzo."),
    ("s3_correggi", 3, "Controlla e correggi", "Tocca un'offerta per correggerla, aggiungere una condizione o metterla in evidenza. Il bordo giallo segnala i prezzi da verificare."),
    ("s4_testi", 4, "Testi pronti per i social", "Post per Instagram e Facebook, messaggio WhatsApp e newsletter: li copi, li modifichi e li approvi. Nulla esce senza il tuo ok."),
    ("s5_video", 5, "Il video si crea da solo", "Un clic e il montatore crea il Reel per Instagram e TikTok, o il video per gli schermi del negozio, in meno di un minuto."),
    ("s6_clienti", 6, "Messaggi personali ai clienti", "Registri i clienti con il loro consenso: ognuno riceve le offerte delle categorie che preferisce. Chi risponde STOP viene tolto subito."),
    ("s7_fine", None, "Tutto in un unico posto", "Ogni settimana: carichi il volantino, controlli, approvi. Al resto pensano gli agenti."),
]

parts = []
still(C / "00_titolo.png", 4.5, OUT / "p00.mp4"); parts.append("p00.mp4")
still(C / "01_problema.png", 7.5, OUT / "p01.mp4"); parts.append("p01.mp4")
still(C / "02_soluzione.png", 7.5, OUT / "p02.mp4"); parts.append("p02.mp4")
for i, (name, step, title, text) in enumerate(STEPS):
    cap = C / f"cap_{name}.png"
    caption(cap, step, title, text)
    speed = 1.35 if name == "s5_video" else 1.0
    clip(D / "rec" / f"{name}.webm", cap, OUT / f"p1{i}.mp4", speed=speed)
    parts.append(f"p1{i}.mp4")
still(C / "99_fine.png", 9, OUT / "p99.mp4"); parts.append("p99.mp4")

(OUT / "list.txt").write_text("".join(f"file '{p}'\n" for p in parts))
final = D / "Promovo_video_tutorial.mp4"
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(OUT / "list.txt"),
                "-c", "copy", "-movflags", "+faststart", str(final)], check=True)
print(final, round(duration(final), 1), "secondi")
