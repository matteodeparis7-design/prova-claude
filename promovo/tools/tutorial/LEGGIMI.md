# Video tutorial di Promovo

Rigenera il video tutorial dal programma vero (utile dopo ogni modifica alla grafica).

1. Avvia un'istanza dimostrativa pulita sulla porta 8100 (`python -m promovo --demo --port 8100`)
   ed elimina il volantino di prova, così il tutorial parte da zero.
2. Metti in questa cartella di lavoro un volantino `volantino_settimana.pdf`.
3. `node record.js <cartella>`: registra i 7 segmenti con cursore visibile (serve Playwright).
4. `python build.py <cartella>`: aggiunge schede, didascalie e dissolvenze e crea
   `Promovo_video_tutorial.mp4` (1280x720, circa 2 minuti e mezzo).
