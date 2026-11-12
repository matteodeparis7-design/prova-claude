# Il sistema di elaborazione {#architettura}

*(slide lezioni 1-3 e "Cenni sul linguaggio macchina"; testo1 cap. 1, 2, 4.1-4.4)*

Prima di programmare bisogna sapere **che cosa** esegue i programmi. Questo capitolo è teoria che può uscire all'orale.

## La macchina di Von Neumann

Quasi tutti i calcolatori seguono lo schema di **Von Neumann**: **i dati e il programma stanno nella stessa memoria**, e una CPU esegue le istruzioni una dopo l'altra.

```text
            +---------------------------------------------+
            |                    CPU                      |
            |  +--------+   +---------------------------+ |
            |  |   CU   |   |  registri: R0 ... R8      | |
            |  | (unita`|   |  PC  (Program Counter)    | |
            |  | di con-|   |  IR  (Instruction Reg.)   | |
            |  | trollo)|   |  RC  (registro confronto) | |
            |  +--------+   +---------------------------+ |
            |  +--------------------------------------+   |
            |  |  ALU (unita` aritmetico-logica)     |   |
            |  +--------------------------------------+   |
            +----------------------+----------------------+
                                   |   BUS (dati, indirizzi, controllo)
       +---------------------------+-----------------------------+
       |                           |                             |
+--------------+         +-------------------+        +-------------------+
| MEMORIA      |         | PERIFERICHE DI    |        | MEMORIA DI MASSA  |
| CENTRALE     |         | INPUT / OUTPUT    |        | (disco, SSD):     |
| (RAM):       |         | tastiera, video,  |        | file permanenti   |
| dati+codice  |         | stampante...      |        |                   |
+--------------+         +-------------------+        +-------------------+
```

- **CPU** (Central Processing Unit), il "cervello":
  - **CU** (Control Unit): legge le istruzioni, le **decodifica** e comanda le altre parti;
  - **ALU** (Arithmetic Logic Unit): fa i calcoli (somme, confronti, operazioni logiche);
  - **registri**: piccole memorie velocissime dentro la CPU. I più importanti: **PC** (*Program Counter*: contiene l'**indirizzo** della prossima istruzione) e **IR** (*Instruction Register*: contiene l'istruzione in esecuzione).
- **Memoria centrale (RAM)**: una lunga sequenza di **locazioni**, ognuna con un **indirizzo** (un numero). È **volatile**: si svuota quando spegni.
- **Memoria di massa** (disco, SSD): lenta ma **permanente**; contiene i file.
- **Periferiche**: input (tastiera, mouse), output (video, stampante).
- **Bus**: i "fili" che collegano tutto (trasportano dati, indirizzi e segnali di controllo).

## Il ciclo Fetch - Decode - Execute

La CPU ripete all'infinito tre passi:

1. **Fetch** (prelievo): legge dalla RAM l'istruzione all'indirizzo scritto nel **PC** e la copia in **IR**; poi il PC viene fatto avanzare all'istruzione successiva.
2. **Decode** (decodifica): la CU capisce che istruzione è (dal suo **codice operativo**) e attiva il circuito giusto.
3. **Execute** (esecuzione): l'istruzione viene eseguita (un calcolo nella ALU, un trasferimento RAM-registro, un salto...).

Un **salto** (*jump*) non fa altro che **scrivere un nuovo indirizzo nel PC**: così la prossima istruzione prelevata non è quella "dopo", ma quella indicata.

## Il linguaggio macchina del corso

A lezione si usa una macchina semplificata con una dozzina di istruzioni. Ogni istruzione è una parola di 32 bit: **8 bit di codice operativo**, poi gli operandi.

| Istruzione | Codice | Formato | Cosa fa |
|---|---|---|---|
| LOAD | `00000000` | codice, registro (4 bit), indirizzo (20 bit) | copia nel registro il contenuto della locazione |
| STORE | `00000001` | codice, registro, indirizzo | copia nella locazione il contenuto del registro |
| ADD | `00000010` | codice, Ri, Rj | Ri = Ri + Rj |
| SUB | `00000100` | codice, Ri, Rj | Ri = Ri - Rj |
| MULT | `00000110` | codice, Ri, Rj | Ri = Ri * Rj |
| DIV | `00001000` | codice, Ri, Rj | Ri = Ri / Rj |
| MOD | `00001010` | codice, Ri, Rj | resto della divisione |
| READ | `00010000` | codice, unità (4 bit), indirizzo | legge un dato da input nella locazione |
| WRITE | `00010001` | codice, unità, indirizzo | manda in output il dato della locazione |
| COMP | `00100000` | codice, Ri, Rj | in RC: -1 se Ri<Rj, 0 se uguali, 1 se Ri>Rj |
| JMP (salto condizionato) | `00100001` | codice, Ri, Rj, indirizzo | se Ri == Rj mette l'indirizzo nel PC |
| STOP | `10000001` | codice | termina il programma |

**Esempio della lezione**: sommare le parole di indirizzo 64 e 68 e mettere il risultato all'indirizzo 60.

```text
00000000 0000 00000000000001000000   LOAD  R0 <- RAM[64]
00000000 0001 00000000000001000100   LOAD  R1 <- RAM[68]
00000010 0000 0001                   ADD   R0 <- R0 + R1
00000001 0000 00000000000000111100   STORE RAM[60] <- R0
10000001                             STOP
```

Per eseguirlo ("RUN") si mette nel PC l'indirizzo della prima istruzione; da lì parte il ciclo fetch-decode-execute.

## Il software di base

- **Sistema operativo (SO)**: il programma che gestisce la macchina e la mette a disposizione degli altri programmi: gestisce i processi (programmi in esecuzione), la memoria, le periferiche e il **file system**.
- **File system**: organizza i dati della memoria di massa in **file** e **cartelle** (directory) in una struttura ad albero. Un file si identifica con il suo **percorso** (es. `C:\esercizi\voli.c`).

## Dal programma C al programma eseguibile

Il processore capisce solo il linguaggio macchina. Un programma scritto in un **linguaggio ad alto livello** come il C va **tradotto**:

```text
 voli.c  --[preprocessore]-->  (testo con #include e #define espansi)
         --[compilatore]--->   voli.o   (codice oggetto, linguaggio macchina)
         --[linker]-------->   voli.exe (eseguibile: unito alle librerie, es. printf)
         --[loader del SO]->   caricato in RAM ed eseguito
```

- Il **preprocessore** gestisce le righe che iniziano con `#` (`#include <stdio.h>`, `#define N 10`).
- Il **compilatore** controlla il programma e lo traduce. Se trova errori **non produce** l'eseguibile.
- Il **linker** collega il tuo codice con quello delle librerie (ad esempio il codice di `printf`).
- Un **IDE** come **Dev-C++** (usato al corso) fa tutto con un clic e include un **debugger**.

::: esame Domande d'orale tipiche
"Descrivi l'architettura di Von Neumann." "Cosa contengono PC e IR?" "Cosa succede nel ciclo fetch-decode-execute?" "Che differenza c'è tra compilatore e linker?" "Cosa fa un'istruzione di salto?" Rispondi con il disegno e con un esempio.
:::

::: esercizio Esercizio 1.1
Scrivi in linguaggio macchina (con i codici della tabella) un programma che legge due numeri dall'unità di input `0000` nelle locazioni 100 e 104, li moltiplica e scrive il risultato nella locazione 108, poi lo manda all'unità di output `0001`.
:::

::: soluzione
```text
00010000 0000 <ind. 100>    READ  RAM[100] <- input
00010000 0000 <ind. 104>    READ  RAM[104] <- input
00000000 0000 <ind. 100>    LOAD  R0 <- RAM[100]
00000000 0001 <ind. 104>    LOAD  R1 <- RAM[104]
00000110 0000 0001          MULT  R0 <- R0 * R1
00000001 0000 <ind. 108>    STORE RAM[108] <- R0
00010001 0001 <ind. 108>    WRITE output <- RAM[108]
10000001                    STOP
```
Gli indirizzi in binario su 20 bit sono: 100 = `00000000000001100100`, 104 = `00000000000001101000`, 108 = `00000000000001101100`.
:::
