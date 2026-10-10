# Video Superfreddo – VERSIONE B (volantino 13-22 ottobre 2026)

Stile "spot TV": fondo ghiaccio chiaro, pannelli diagonali colorati per reparto, pagine che scorrono in 3D
e 25 prodotti protagonisti scontornati a tutto schermo con cartellino prezzo animato.

| File | Uso |
|---|---|
| `4K_parti/SuperFreddo_B_4K_parte00…13.mp4` | **Master 4K 3840x2160, 25 fps** per il maxi schermo, in 14 parti da 20 s (limite di GitHub) |
| `SuperFreddo_VersioneB_FullHD_25fps.mp4` | Versione Full HD 1920x1080 in un unico file |
| `ANTEPRIMA_VersioneB_720p.mp4` | Anteprima leggera |

Durata 4:32 · H.264 + AAC 320k · audio -14 LUFS · pensato per girare in loop.

## Riunire le parti 4K (senza perdita di qualità)
```
(for %f in (4K_parti\*.mp4) do @echo file '%f') > lista.txt          (Windows)
for f in 4K_parti/*.mp4; do echo "file '$f'"; done > lista.txt        (Mac/Linux)
ffmpeg -f concat -safe 0 -i lista.txt -c copy SuperFreddo_B_4K_completo.mp4
```

## Sequenza
Intro → copertina (Burger di salmone) → per ogni pagina: titolo reparto, pagina che scorre, 4 prodotti protagonisti →
spot Over 65 dopo pagina 4 → spot Essere Decò dopo pagina 7 → Super Concorso → chiusura Colleferro + QR app.

Prezzi e nomi presi direttamente dal testo del PDF. Musica originale (pianoforte, marimba, glockenspiel, archi;
campioni FluidR3 GM con licenza MIT) composta per questo video, nessun diritto di terzi.
