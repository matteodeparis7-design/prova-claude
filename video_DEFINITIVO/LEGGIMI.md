# Video Superfreddo – VERSIONE DEFINITIVA (volantino 13-22 ottobre 2026)

Basata sulla Versione A, con 3 animazioni illustrate, la scena "Prodotti Anniversario" in grafica dorata
e ritagli delle offerte rifiniti uno per uno (prodotto, prezzo e icone di cottura completi, nessun frammento).
Punto vendita: Colleferro, Via dei Pioppi 24.

| File | Uso |
|---|---|
| `4K_parti/SuperFreddo_DEFINITIVO_4K_parte00…12.mp4` | **Master 4K 3840x2160, 25 fps** per i maxi schermi, in 13 parti da 20 s (limite di GitHub) |
| `SuperFreddo_DEFINITIVO_FullHD_25fps.mp4` | Versione Full HD 1920x1080 in un unico file |
| `ANTEPRIMA_DEFINITIVO_720p.mp4` | Anteprima leggera |

Durata 4:20 · H.264 + AAC 320k · audio -14 LUFS · pensato per girare in loop.

## Riunire le parti 4K (senza perdita di qualità)
```
(for %f in (4K_parti\*.mp4) do @echo file '%f') > lista.txt          (Windows)
for f in 4K_parti/*.mp4; do echo "file '$f'"; done > lista.txt        (Mac/Linux)
ffmpeg -f concat -safe 0 -i lista.txt -c copy SuperFreddo_DEFINITIVO_4K.mp4
```

## Sequenza
| Tempo | Scena |
|---|---|
| 0:00 | Intro logo Decò 20 anni + Superfreddo |
| 0:08 | Copertina |
| 0:16 | **Prodotti Anniversario** (Sofficini, McCain, Magnum) in grafica dorata |
| 0:22 | **Animazione pesce**: pescato → congelato in un blocco di ghiaccio → riposto nel banco frigo |
| 0:30 | Pagine 2-4 (pescato, sfiziosità) |
| 1:24 | Spot Over 65 |
| 2:00 | Pagina 5 |
| 2:18 | **Animazione cornetto inzuppato nel latte** → "La colazione è servita!" |
| 2:26 | Pagina 6 (pasticceria) |
| 2:44 | **Animazione freezer** che si apre sulle grandi marche |
| 2:52 | Pagina 7 (confezionati) |
| 3:10 | Carta Essere Decò: nuova presentazione animata (1 € = 1 punto, sconti e premi, prezzi con carta, gratuita e personale, come richiederla) + animazione app originale |
| 3:56 | Pagina 8 (Super Concorso, Colleferro evidenziato) |
| 4:10 | Chiusura: Ti aspettiamo a Colleferro, Via dei Pioppi 24 + QR app |

Animazioni disegnate in vettoriale; musica originale con effetti sonori sincronizzati, nessun diritto di terzi.
