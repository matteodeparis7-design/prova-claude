# Formulario, glossario e autoverifica {#formulario}

::: obiettivi Cosa imparerai
- tutte le formule e gli schemi da ripassare il giorno prima
- come verificare da solo se sei pronto
:::

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

## Glossario

I termini del corso in una riga. Se un termine non ti è chiaro, torna al capitolo indicato.

<dl class="glossario">
<dt>Algoritmo</dt><dd>Sequenza finita di passi precisi che risolve un problema (cap. 3).</dd>
<dt>ALU</dt><dd>Parte della CPU che esegue calcoli e confronti (cap. 1).</dd>
<dt>Array</dt><dd>Sequenza di elementi dello stesso tipo in locazioni consecutive, indici da 0 a N-1 (cap. 6).</dd>
<dt>Caso base</dt><dd>Il caso che una funzione ricorsiva risolve senza richiamarsi (cap. 11).</dd>
<dt>Cast</dt><dd>Conversione esplicita di tipo, es. <code>(double) somma</code> (cap. 3).</dd>
<dt>Chiave</dt><dd>Campo che identifica in modo univoco un elemento di una tabella (cap. 10).</dd>
<dt>Compilatore</dt><dd>Programma che traduce il sorgente C in linguaggio macchina (cap. 1).</dd>
<dt>Complemento a due</dt><dd>Rappresentazione degli interi con segno usata dai calcolatori (cap. 2).</dd>
<dt>Debugging</dt><dd>Ricerca e correzione degli errori di un programma (Laboratorio, cap. 13).</dd>
<dt>Deallocazione</dt><dd>Restituzione della memoria allocata dinamicamente, con <code>free</code> (cap. 9).</dd>
<dt>Eccesso 127</dt><dd>Modo di scrivere l'esponente dei float: esponente vero + 127 (cap. 2).</dd>
<dt>Esecuzione simulata</dt><dd>Esecuzione "a mano" di un programma, annotando i valori delle variabili (cap. 4).</dd>
<dt>Flag</dt><dd>Variabile che vale 0 finché accade un evento, poi 1; usata per fermare i cicli (cap. 4).</dd>
<dt>Floating point</dt><dd>Rappresentazione dei reali con segno, esponente e mantissa (cap. 2).</dd>
<dt>Heap</dt><dd>Zona di memoria da cui <code>malloc</code> prende i blocchi (cap. 9).</dd>
<dt>Lista collegata</dt><dd>Sequenza di nodi allocati dinamicamente, ognuno col puntatore al successivo (cap. 14).</dd>
<dt>Linker</dt><dd>Programma che unisce il codice compilato con le librerie e crea l'eseguibile (cap. 1).</dd>
<dt>Memory leak</dt><dd>Memoria allocata e mai liberata, di cui si è perso l'indirizzo (cap. 9).</dd>
<dt>NULL</dt><dd>Valore di un puntatore che non punta a nulla; la lista vuota (cap. 8, 14).</dd>
<dt>Parametro attuale</dt><dd>Espressione scritta nella chiamata; il suo valore viene copiato (cap. 5).</dd>
<dt>Parametro formale</dt><dd>Variabile dichiarata nell'intestazione della funzione (cap. 5).</dd>
<dt>Parametro di output</dt><dd>Parametro puntatore usato per restituire un risultato al chiamante (cap. 8).</dd>
<dt>PC (Program Counter)</dt><dd>Registro con l'indirizzo della prossima istruzione (cap. 1).</dd>
<dt>Processo</dt><dd>Un programma in esecuzione (cap. 1).</dd>
<dt>Prototipo</dt><dd>Dichiarazione di una funzione: tipo, nome, tipi dei parametri (cap. 5).</dd>
<dt>Pseudocodice</dt><dd>Algoritmo scritto in italiano a passi numerati, prima del codice (cap. 3).</dd>
<dt>Puntatore</dt><dd>Variabile che contiene un indirizzo di memoria (cap. 8).</dd>
<dt>Record di attivazione (RDA)</dt><dd>Zona di memoria creata a ogni chiamata, con parametri e variabili locali (cap. 5, 11).</dd>
<dt>Record generatore</dt><dd>Nodo fittizio messo in testa a una lista per eliminare il caso speciale del primo nodo (cap. 14).</dd>
<dt>Ricorsione</dt><dd>Funzione che chiama se stessa su un problema più piccolo (cap. 11).</dd>
<dt>Scatola nera / trasparente</dt><dd>Metodi di test basati sulla specifica / sul codice (cap. 13).</dd>
<dt>Sentinella</dt><dd>Valore speciale che segna la fine dei dati in input, es. 0 (cap. 4).</dd>
<dt>Stringa esatta</dt><dd>Stringa allocata con <code>malloc(strlen+1)</code>, senza spreco (cap. 9).</dd>
<dt>Struct</dt><dd>Record che raggruppa campi di tipi diversi (cap. 10).</dd>
<dt>Stub</dt><dd>Versione finta di una funzione usata nel test top-down (cap. 13).</dd>
<dt>Tabella</dt><dd>Struttura dati che rappresenta un archivio: aggiungi, elimina, modifica, cerca (cap. 10).</dd>
<dt>Tipo di dato astratto (ADT)</dt><dd>Tipo definito dalle operazioni, indipendente da come è memorizzato (cap. 10).</dd>
<dt>typedef</dt><dd>Istruzione che dà un nuovo nome a un tipo esistente (cap. 10).</dd>
<dt>Visita di un albero</dt><dd>Esame di tutti i nodi: preordine, inordine, postordine (cap. 15).</dd>
</dl>

## Autoverifica: sei pronto se...

Prima di iscriverti all'appello, controlla di saper fare **ognuna** di queste cose **senza guardare il fascicolo**. Se una ti manca, torna al capitolo indicato.

::: esame Esercizi 1 e 2 (23 punti)
- [ ] Dal testo di una traccia, scrivo i tipi corretti (stringa esatta, stringa fissa, lista) in meno di 15 minuti. *(cap. 16, 17)*
- [ ] Scrivo una funzione che scorre una lista e restituisce 3 risultati (uno col `return`, due con parametri puntatore). *(cap. 8, 14)*
- [ ] Scrivo a memoria: inserimento in testa, in coda (con e senza record generatore), ordinato, eliminazione di un nodo, eliminazione di tutti i nodi con una proprietà, deallocazione. *(cap. 14, 18)*
- [ ] Riempio un nodo con una stringa esatta (`malloc(strlen+1)` + `strcpy`) e la libero prima del nodo. *(cap. 9)*
- [ ] Per ogni funzione che scrivo, controllo i casi: lista vuota, primo, ultimo, in mezzo, assente. *(cap. 16)*
- [ ] Ho svolto su carta, a tempo (2h30), almeno 3 tracce (Guasti, Marmotte, Biblioteca o Officina) e le ho corrette. *(cap. 17, 18)*
:::

::: esame Esercizio 3 (7 punti)
- [ ] Descrivo i metodi a scatola nera e trasparente e progetto una tabella di test motivati per una funzione data. *(cap. 13, 17)*
- [ ] Converto un reale in floating point a 32 bit (e viceversa) senza errori, verificando il risultato. *(cap. 2)*
- [ ] Converto in complemento a due con il numero minimo di bit ed eseguo somme e sottrazioni. *(cap. 2)*
- [ ] Scrivo una funzione ricorsiva su lista o array e ne disegno la pila dei record di attivazione, andata e ritorno. *(cap. 11, 17)*
- [ ] Scrivo le tre visite di un albero e le applico a un albero di 9 nodi. *(cap. 15)*
:::

::: esame Orale
- [ ] So spiegare ogni riga del mio scritto e correggerne gli errori.
- [ ] Rispondo a voce, con un disegno, alle domande del capitolo 19 (Von Neumann, RDA, passaggio dei parametri, puntatori e array, memoria dinamica, file, ordinamenti, ricorsione, test, liste).
- [ ] So scrivere un algoritmo in pseudocodice, disegnarne il diagramma di flusso e farne l'esecuzione simulata. *(cap. 3, 4)*
:::

Se hai spuntato tutto, sei pronto per l'esame.


::: ricorda Da ricordare
- Se sai fare tutto l'elenco dell'autoverifica **senza guardare**, sei pronto.
:::

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
