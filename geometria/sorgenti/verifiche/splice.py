"""Sostituisce il blocco di un esercizio (o della teoria) in un file d'appello.
uso: python3 splice.py <file_appello.html> <1..5|TEORIA> <file_nuovo_blocco.html>
Il blocco va dal suo marcatore fino al marcatore successivo, al riquadro
'Prova teorica' finale o a </section> (il primo che si incontra)."""
import sys
path, key, newf = sys.argv[1:4]
s = open(path, encoding="utf-8").read()
mk = ("<!-- ======================= TEORIA ======================= -->" if key == "TEORIA"
      else f"<!-- ======================= ESERCIZIO {key} ======================= -->")
assert s.count(mk) == 1, f"marcatore non trovato o duplicato: {mk}"
start = s.index(mk) + len(mk)
ends = [i for i in (s.find("<!-- =======================", start),
                    s.find('<div class="nota"><p><b>Prova teorica', start),
                    s.find("</section>", start)) if i != -1]
end = min(ends)
new = open(newf, encoding="utf-8").read().strip()
s = s[:start] + "\n" + new + "\n\n" + s[end:]
open(path, "w", encoding="utf-8").write(s)
print(f"OK {path} blocco {key}: sostituiti {end-start} caratteri con {len(new)}")
