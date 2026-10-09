# Video Superfreddo – Volantino 13-22 ottobre 2026

| File | Uso |
|---|---|
| `4K_parti/SuperFreddo_4K_parte00…11.mp4` | **Master 4K 3840x2160, 25 fps** per il maxi schermo, diviso in 12 parti da 20 s (limite di GitHub) |
| `SuperFreddo_Volantino_13-22ott_FullHD_25fps.mp4` | Versione Full HD 1920x1080 in un unico file |
| `ANTEPRIMA_SuperFreddo_720p.mp4` | Anteprima leggera da guardare sul telefono |

Durata: 3:50. Formato H.264 + AAC 320k, audio a -14 LUFS. Il video è pensato per girare in loop: inizio e fine stanno sullo stesso sfondo.

## Riunire le parti 4K in un solo file (senza perdita di qualità)

Con [ffmpeg](https://ffmpeg.org), dalla cartella `video`:

```
(for %f in (4K_parti\*.mp4) do @echo file '%f') > lista.txt          (Windows)
for f in 4K_parti/*.mp4; do echo "file '$f'"; done > lista.txt        (Mac/Linux)
ffmpeg -f concat -safe 0 -i lista.txt -c copy SuperFreddo_4K_completo.mp4
```

Se il lettore del maxi schermo accetta le playlist, si possono caricare direttamente le 12 parti in ordine.

## Sequenza
Intro con logo → copertina → pagine 2-4 → spot Over 65 → pagine 5-7 → spot Essere Decò → pagina 8 (concorso + punti vendita, Colleferro evidenziato) → chiusura Colleferro, Via dei Pioppi 24 + QR app Decò.

Musica originale composta e sintetizzata da zero per questo video (nessun diritto di terzi). Gli script di generazione sono in `sorgenti/`.
