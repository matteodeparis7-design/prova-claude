#!/bin/bash
# Avvio di Promovo su Mac: doppio clic su questo file.
cd "$(dirname "$0")/promovo" || exit 1
echo
echo "  ============================================="
echo "   PROMOVO - avvio sul tuo computer"
echo "  ============================================="
echo
if ! command -v python3 >/dev/null 2>&1 || ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >/dev/null 2>&1; then
  echo "  Per usare Promovo serve Python 3.11 o piu' recente."
  echo "  Si apre ora la pagina di Python: scarica e installa la versione per macOS,"
  echo "  poi riapri questo file."
  open "https://www.python.org/downloads/"
  read -r -p "  Premi Invio per chiudere."
  exit 1
fi
if [ ! -x .venv/bin/python ]; then
  echo "  Prima installazione: servono alcuni minuti, solo questa volta."
  python3 -m venv .venv || { read -r -p "  Errore: fai una foto e mandala in chat. Invio per chiudere."; exit 1; }
fi
echo "  Controllo dei componenti..."
.venv/bin/python -m pip install --quiet --upgrade pip >/dev/null 2>&1
.venv/bin/python -m pip install --quiet --upgrade . || { read -r -p "  Errore: fai una foto e mandala in chat. Invio per chiudere."; exit 1; }
# La chiave dell'IA si può incollare nel file CHIAVE_IA.txt, accanto a questo file.
if [ -z "$ANTHROPIC_API_KEY" ] && [ -f "$(dirname "$0")/CHIAVE_IA.txt" ]; then
  export ANTHROPIC_API_KEY="$(head -n 1 "$(dirname "$0")/CHIAVE_IA.txt" | tr -d '[:space:]')"
fi
[ -z "$ANTHROPIC_API_KEY" ] && export PROMOVO_AI=off
echo
echo "  Promovo si sta avviando: il browser si aprira' appena e' pronto."
echo "  Accesso di prova:  demo@promovo.it  /  promovo2026"
echo
echo "  NON chiudere questa finestra mentre usi Promovo. Per spegnerlo, chiudila."
echo
.venv/bin/python -m promovo --demo --open
