# Fascicolo di Tecniche della Programmazione

Fascicolo di preparazione all'esame di *Tecniche della Programmazione* (prof. Marco Temperini, Ingegneria dell'Informazione, sede di Latina, A.A. 2026/27).

- `Fascicolo-Tecniche-della-Programmazione.pdf`: versione da stampare (A4, soluzioni visibili).
- `fascicolo.html`: versione web, con indice, caselle "studiato" e soluzioni a scomparsa.
- `capitoli/`: il testo dei capitoli (Markdown).
- `codice/`: tutti i programmi C del fascicolo, completi e compilabili (in `codice/palestra/` i 25 esercizi graduati).
- `build/`: lo script che compone HTML e PDF.

## Provare il codice

Ogni file in `codice/` ha un `main` di prova:

```bash
gcc -std=c89 -pedantic -Wall codice/liste.c -o liste && ./liste
```

In Dev-C++ basta aprire il file `.c` e compilare (con l'opzione "Supporto programmi ANSI standard C").

## Rigenerare il fascicolo

```bash
pip install markdown pygments
python3 build/build.py
```
