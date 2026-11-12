# Formulario da ripassare il giorno prima {#formulario}

## Rappresentazione

| Cosa | Formula / regola |
|---|---|
| binario puro, n bit | [0, 2<sup>n</sup> - 1] |
| modulo e segno, n bit | [-(2<sup>n-1</sup> - 1), 2<sup>n-1</sup> - 1], due zeri |
| complemento a 2, n bit | [-2<sup>n-1</sup>, 2<sup>n-1</sup> - 1]; negativo: inverti i bit e somma 1 |
| float 32 bit | 1 segno, 8 esponente (eccesso 127), 23 mantissa: (-1)<sup>s</sup> × 1.M × 2<sup>E-127</sup> |
| potenze di 2 | 2<sup>7</sup>=128, 2<sup>8</sup>=256, 2<sup>10</sup>=1024, 2<sup>11</sup>=2048, 2<sup>15</sup>=32768, 2<sup>16</sup>=65536 |
| ASCII | '0'=48, 'A'=65, 'a'=97, '\0'=0 |

## C in una pagina

```c
printf("%d %c %f %s %lf\n", ...);   scanf("%d %lf %s", &i, &d, stringa);
/* divisione intera: 7/2 == 3;  reale: (double) a / b                      */
/* stringhe: strlen strcpy strcmp(a,b)==0 strcat  (string.h)              */
/* memoria:  p = malloc(n * sizeof(T)); if (p == NULL) ...; free(p);       */
/* file:     f = fopen(nome, "r"); if (f == NULL) ...; fscanf(...) == 1; fclose(f); */
/* struct:   s.campo   p->campo  == (*p).campo                             */
/* output:   void f(int *out) { *out = ...; (*out)++; }    f(&x);         */
```

## Lo schema dei tipi per l'esame

```c
typedef struct {
  char *nome;               /* lunghezza ignota -> stringa esatta         */
  char codice[K + 1];       /* K caratteri                                */
  int numero;
  char tipo;
} TipoElemento;

struct nodo { TipoElemento info; struct nodo *next; };
typedef struct nodo TipoNodo;
typedef TipoNodo *TipoLista;
```

## Gli schemi sulle liste

```c
/* scansione */
for (p = l; p != NULL; p = p->next) ...

/* inserimento in testa */
n = malloc(sizeof(TipoNodo)); n->info = x; n->next = *pl; *pl = n;

/* due puntatori (per inserire prima di / eliminare corr) */
prec = NULL; corr = *pl;
while (corr != NULL && <non e` il posto/nodo giusto>) { prec = corr; corr = corr->next; }

/* agganciare un nuovo nodo prima di corr */
n->next = corr;  if (prec == NULL) *pl = n; else prec->next = n;

/* scavalcare ed eliminare corr */
if (prec == NULL) *pl = corr->next; else prec->next = corr->next;
free(corr->info.nome); free(corr);

/* record generatore */
TipoNodo rg; rg.next = *pl; p = &rg; ... ; *pl = rg.next;

/* ricorsione */
if (l == NULL) return <caso base>;  return <uso l->info> f(l->next);

/* deallocazione */
while (*pl != NULL) { d = *pl; *pl = d->next; free(d); }
```

## Test

- **Scatola nera**: dalla specifica; classi di equivalenza dell'input; un rappresentante per classe; casi limite (vuota, un elemento, primo, ultimo, assente, uguale alla soglia).
- **Scatola trasparente**: dal codice; copertura di istruzioni → decisioni (V e F) → condizioni (V e F) → valori limite; cicli con 0, 1, più iterazioni.
- **Test** = dati di prova + output atteso, confronto con l'output effettivo; se diversi, debugging.

## Ricorsione

Caso base + caso ricorsivo che si avvicina al caso base. RDA: una per chiamata, impilate; si risolve all'andata fino al caso base, i valori tornano indietro al ritorno.

## Il giorno dell'esame

- Documento d'identità, iscrizione su Infostud fatta, homework accettati.
- Leggi tutto il testo, poi i tipi, poi `eser1`, `eser2`, esercizio 3, rilettura con la checklist del capitolo 16.
- Scrivi in modo ordinato e commenta l'algoritmo.

## Fonti

Materiale consultato sul sito del corso (prof. Marco Temperini), A.A. 2026/27:

- [Pagina del corso](https://www.diag.uniroma1.it/marte/homepage/didattica/tdp-latina.html) e [pagina didattica del docente](https://www.diag.uniroma1.it/marte/homepage/teachingmt.html)
- [Programma 2026/27](https://www.diag.uniroma1.it/marte/homepage/didattica/tdp-latina/2026-27-TDP-Programma.html)
- [Calendario e contenuto delle lezioni](https://www.diag.uniroma1.it/marte/homepage/didattica/tdp-latina/lezioniTdP.html)
- [Regole e date d'esame](https://www.diag.uniroma1.it/marte/homepage/didattica/tdp-latina/tdp-esami.html) e [testi d'esame d'esempio](https://www.diag.uniroma1.it/marte/homepage/didattica/tdp-latina/tdp-esami/)
- [Homework](https://www.diag.uniroma1.it/marte/homepage/didattica/tdp-latina/homework_TdP_management.html)
- Slide delle lezioni (cartella `tdp-lezioni`), complementi didattici, esercitazioni guidate EG1-EG9
- Scheda del docente su [corsidilaurea.uniroma1.it](https://corsidilaurea.uniroma1.it/it/users/marcotemperiniuniroma1it)

Al momento della consultazione (novembre 2026) le slide sulle liste (lezioni 21-25) e le EG10-EG11 dell'anno in corso non erano ancora pubblicate: il capitolo sulle liste segue gli argomenti elencati nel calendario delle lezioni e il testo2 (Calvanese et al.), che il corso adotta per quella parte. Quando escono le slide, confrontale con il capitolo 14 e adotta i nomi usati dal professore.

Questo fascicolo è un aiuto allo studio: non sostituisce le lezioni, i libri di testo e le comunicazioni ufficiali su Classroom.
