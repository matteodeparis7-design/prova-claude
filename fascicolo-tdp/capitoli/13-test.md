# Qualità dei programmi e test di correttezza {#test}

*(lezione 12, solo online, con video; slide "Qualità e Testing"; testo2 cap. 1-2)*

::: obiettivi Cosa imparerai
- le qualità di un programma e i tipi di errore
- progettare test a scatola nera e a scatola trasparente
- rispondere all'esercizio 3 sui test
:::

Questo argomento esce spesso come **esercizio 3** ("descrivere il metodo a scatola nera / trasparente e applicarlo a `eser1`"). Vale fino a 7 punti e si prepara bene in anticipo.

## Le qualità di un programma

- **Efficienza**: quanto **tempo** impiega e quanto **spazio** (memoria) usa. Si gestisce studiando l'algoritmo e la sua complessità.
- **Robustezza**: il programma funziona anche con **usi anomali** (input sbagliato, file mancante, memoria esaurita). Si gestisce controllando i dati in ingresso, chiedendo l'input in modo chiaro, controllando `NULL` dopo `malloc` e `fopen`.
- **Correttezza**: il programma **fa quello che ci si aspetta**. Si verifica con i **test**.

## Gli errori

| Tipo | Quando si scopre | Esempio |
|---|---|---|
| **lessicale** | compilazione | `returna x;` (parola che non esiste) |
| **sintattico** | compilazione | `foor (i=0; ...)`, `;` mancante |
| **semantico** | compilazione | `int i = 8.4;` (tipi incompatibili), variabile non dichiarata |
| **logico / di codifica** | **solo con i test** | `prod = prod + i` invece di `prod = prod * i`; `i <= i` invece di `i <= n` |

Il compilatore segnala un errore **dopo** averlo trovato: la riga sbagliata può essere **prima** di quella indicata.

Un programma che compila **non è detto che sia corretto**. Bisogna testarlo.

## Che cos'è un test

**Test** = (1) eseguire il programma con certi **dati di prova**; (2) confrontare l'**output atteso** (calcolato a mano prima) con l'**output effettivo**. Se coincidono si passa al test successivo; se no si fa **debugging**: si ispeziona il codice, si aggiungono stampe delle variabili (**metodo delle stampe**), si usa il **debugger** (watch sulle variabili, esecuzione passo passo, call stack).

**Test fatti a caso non bastano.** L'esempio del professore:

```c
int uguali(char p1[4], char p2[4]) {     /* SBAGLIATA */
  int u, i;
  for (i = 0; i < 4; i++)
    if (p1[i] != p2[i])
      u = 0;
    else
      u = 1;                             /* questo else e` l'errore */
  return u;
}
```

| Test | Input | Atteso | Effettivo |
|---|---|---|---|
| 1 (diverse) | PERA, TRAM | 0 | 0 |
| 2 (uguali) | PERA, PERA | 1 | 1 |
| 3 (diverse, ultima lettera uguale) | PERA, MELA | 0 | **1** |

I primi due test passano, eppure la funzione è sbagliata: conta solo l'**ultimo** confronto. Serve un **metodo** per scegliere i test **prima** di farli. I metodi sono due.

## Metodo a scatola nera (copertura dell'input)

Si scelgono i test **guardando solo la specifica** (che cosa deve fare la funzione), **senza guardare il codice**.

1. Si **partiziona** l'insieme dei possibili input in **classi di equivalenza**: input di una stessa classe dovrebbero essere trattati "allo stesso modo" (stesso tipo di output atteso).
2. Si sceglie **un rappresentante per classe**: un test per ogni classe.
3. Più le classi sono **specifiche**, più test si fanno e più si è sicuri. Bisogna considerare in particolare i **casi limite**: struttura vuota, un solo elemento, elemento cercato in prima / ultima posizione, assente, valori uguali alla soglia...

Esempio (lezione) per `indiceVolo(TipoTabella t, char *codice)`: tabella vuota; tabella piena e codice presente; tabella piena e codice assente; codice presente in prima posizione; codice presente in ultima posizione; codice presente in mezzo...

## Metodo a scatola trasparente (copertura del codice)

Si scelgono i test **guardando il codice**, in modo che, nel complesso, i test **mettano in azione le sue parti**. Ci sono criteri via via più scrupolosi:

1. **Copertura delle istruzioni**: alla fine dei test **ogni istruzione** è stata eseguita almeno una volta.
2. **Copertura delle decisioni**: in più, ogni **decisione** (condizione di `if`, `while`, `for`) è stata **vera** almeno una volta **e falsa** almeno una volta.
3. **Copertura delle condizioni**: in più, ogni **condizione elementare** dentro una decisione composta (es. `A<10` e `C<20` in `A<10 || C<20`) è stata vera e falsa almeno una volta.
4. **Valori limite**: si aggiungono test con i valori **al limite** delle condizioni (es. 0, 10, 20) e **vicini** al limite (9, 11, 19, 21, -1, +1).

Per i cicli, si prova anche: **zero iterazioni**, **una** iterazione, **più** iterazioni.

L'esempio della lezione: si voleva "se A ≠ 0 stampa 1; se A < 10 **e** C < 20 stampa 2", ma si è scritto `if (A > 0)` e `if ((A < 10) || (C < 20))`. Il test A=3, C=18 copre tutte le istruzioni ma non trova gli errori; aggiungendo criteri e valori limite (A=-3, A=0, C=20, A=20...) gli errori emergono. **Nessun criterio garantisce di trovare tutti gli errori**: più criteri = più test = più costo, ma più sicurezza.

## Test top-down (per programmi con molte funzioni)

Si fa un **test incrementale**: si prova una funzione alla volta, partendo dal `main`. Le funzioni non ancora provate si sostituiscono con **stub**: versioni finte che restituiscono direttamente il risultato giusto per il test in corso. Se qualcosa va storto, l'errore può essere solo nella funzione che si sta provando.

## Come rispondere all'esercizio 3 (modello)

::: esame Schema di risposta
1. **Descrizione del metodo** (5-8 righe): obiettivo, idea (specifica vs codice), criteri (classi di equivalenza / i 4 criteri di copertura), limiti (nessun metodo garantisce la correttezza).
2. **Tabella dei test** applicata a `eser1`: per ogni test **perché** lo faccio (quale classe / quale istruzione o decisione copre), **dati di prova** concreti (una lista disegnata), **output atteso**.
3. **Esecuzione simulata** di almeno un test, mostrando come cambiano le variabili, e conclusione "output effettivo = atteso".
:::

Una risposta completa, applicata alla funzione `eser1` della traccia dei guasti, è nel capitolo 17.

::: esercizio Esercizio 13.1
Data la funzione `int maxArray(int v[], int dim)` (restituisce il massimo, dim ≥ 1), progetta i test a scatola nera.
:::

::: soluzione
Classi di equivalenza (partizione dell'input) e un rappresentante per ciascuna:

| Test | Classe | Input | Atteso |
|---|---|---|---|
| 1 | un solo elemento | `{7}` | 7 |
| 2 | massimo in prima posizione | `{9, 2, 5}` | 9 |
| 3 | massimo in ultima posizione | `{2, 5, 9}` | 9 |
| 4 | massimo in mezzo | `{2, 9, 5}` | 9 |
| 5 | tutti negativi | `{-4, -2, -8}` | -2 |
| 6 | massimo ripetuto | `{9, 1, 9}` | 9 |
| 7 | tutti uguali | `{3, 3, 3}` | 3 |

Il test 5 scopre l'errore classico `max = 0` come valore iniziale; i test 2 e 3 scoprono errori sugli estremi del ciclo.
:::

::: ricorda Da ricordare
- Test = dati di prova + **output atteso**, confrontato con l'effettivo.
- Nera: dalla **specifica** (classi di equivalenza); trasparente: dal **codice** (istruzioni, decisioni, condizioni, valori limite).
- Nessun metodo garantisce l'assenza di errori.
:::
