# Prima di cominciare: com'è fatto l'esame {#esame}

Questo fascicolo segue il **programma 2026/27** di *Tecniche della Programmazione* del prof. Marco Temperini (Ingegneria dell'Informazione, sede di Latina). L'ho costruito leggendo il sito del corso: programma, calendario delle lezioni, slide, complementi didattici, esercitazioni guidate (EG) e i testi d'esame d'esempio. Tutti i programmi C che trovi qui sono stati compilati e provati in ANSI C (`gcc -std=c89 -pedantic -Wall`), lo standard richiesto dal professore.

## Le regole, in breve

::: esame Cosa serve per sostenere l'esame
- **Homework**: chi si è immatricolato dal 2025/26 in poi (quindi anche tu) deve aver **consegnato e visto accettati i compiti (homework)** su Classroom. Senza homework accettati non puoi presentarti.
- **Iscrizione** alla prova scritta su **Infostud**.
- **Documento di riconoscimento** il giorno dello scritto, altrimenti non sei ammesso.
- Usa **solo l'email istituzionale** (`...@studenti.uniroma1.it`) per Classroom.
:::

L'esame finale ha due parti, di norma in giorni diversi:

1. **Prova scritta**, di **2 ore e 30 minuti** nei testi d'esempio (la pagina degli esami dice "tipicamente alcuni esercizi in due ore"). Si scrive su carta, senza computer.
2. **Prova orale**: si discute lo scritto e possono arrivare domande su tutto il programma. La data dell'orale viene comunicata alla fine dello scritto.

### Gli homework

Un homework è un programma C da scrivere su un "macro-argomento" appena studiato: tabelle con array, tabelle con liste, metodologia di sviluppo, modularizzazione, ricorsione. Il testo esce su Classroom ("Lavori del corso"). Regole del professore:

- consegnali **nell'ordine** in cui sono pubblicati (primo, secondo, ...);
- tra una consegna e l'altra devono passare **almeno 5 giorni**;
- il consiglio è consegnare ogni homework **entro una o due settimane** dalla pubblicazione. Consegnarli tutti alla fine è inutile per imparare, e rischi di non fare in tempo per l'appello (per via dei 5 giorni).

## Com'è fatta la prova scritta

Ho analizzato tutti i testi d'esempio pubblicati. La struttura è **sempre la stessa**, ed è la cosa più importante di questo fascicolo:

| Esercizio | Punti | Cosa chiede (sempre) |
|---|---|---|
| **1** | da 0 a **13** | Definire i **tipi** per una **lista collegata** (record + puntatori) di elementi descritti nel testo, poi scrivere una funzione `eser1` che **scorre la lista** e restituisce **più risultati** (un valore con `return`, gli altri con **parametri di output**). |
| **2** | **10** | Una funzione `eser2` che **modifica la lista**: eliminare un elemento (es. il più importante) oppure **inserire mantenendo l'ordine**. |
| **3** | da **-1** a **7** | Una domanda "di teoria applicata": **test a scatola nera / trasparente** applicato a `eser1`, oppure **rappresentazione floating point** di un numero, oppure una **funzione ricorsiva** con esecuzione simulata e **record di attivazione**, oppure (vecchio programma) **visite di un albero**. |

Totale: 30 punti. Attenzione al **-1** dell'esercizio 3: una risposta sbagliata o confusa può toglierti un punto. Rispondi con ordine.

::: nota Come leggere i testi d'esame
In tutti gli elementi da memorizzare c'è **una stringa "di lunghezza non nota a priori"** (descrizione, cognome e nome...). È un segnale preciso: va rappresentata come `char *` e allocata **esattamente** con `malloc(strlen(...)+1)` (capitolo 9). Ci sono poi **stringhe di lunghezza fissa** ("codice di 9 caratteri", "grado di 8 caratteri"): quelle diventano `char campo[9+1]`. Gli altri campi sono `int`, `char` o `double`.
:::

## Il programma ufficiale, voce per voce

Ogni voce del programma 2026/27 pubblicato dal professore, con il capitolo del fascicolo che la tratta. Spunta le voci man mano che le studi.

| Voce del programma ufficiale | Fonti indicate dal professore | Capitolo |
|---|---|---|
| Architettura: macchina di Von Neumann, CPU, memoria centrale, periferiche | slide, testo1 cap. 1 | 1 |
| Rappresentazione dell'informazione: sistemi numerici, interi, floating point | slide, complementi, testo1 app. D | 2 |
| Linguaggio macchina, assembler, esecuzione di un programma in linguaggio macchina | slide, complementi, testo1 cap. 4.1-4.4 | 1 |
| Software di base: sistema operativo, file system; compilazione ed esecuzione | slide, testo1 cap. 2 | 1 |
| Concetto di algoritmo; variabile; tipi semplici | slide, testo1 cap. 3 e 6 | 3 |
| Operatori, espressioni e loro valutazione | slide, complementi, testo1 cap. 5, 8, app. C | 3 |
| Librerie di funzioni per l'input/output | slide, complementi, testo1 cap. 5, 6, app. B | 3, 7 |
| Programmazione strutturata, istruzioni e blocchi, selezione e iterazione | slide, complementi, testo1 cap. 4, 5, 7, 9 | 3, 4 |
| Array | slide, testo1 cap. 10 | 6 |
| Funzioni, visibilità e ciclo di vita delle variabili | slide, complementi, testo1 cap. 11 | 5 |
| File testuali | slide, video, complementi, testo1 cap. 17 | 7 |
| Puntatori | slide, testo1 cap. 14 | 8 |
| Stringhe di caratteri | slide, testo1 cap. 13 | 9 |
| Allocazione dinamica: malloc, free, realloc; array statici e dinamici | slide, complementi, testo1 cap. 14, app. B | 9 |
| Stringhe con allocazione "esatta" | slide, complementi | 9 |
| Strutture (struct) | slide, testo1 cap. 20 | 10 |
| Ricorsione | slide, complementi, testo1 cap. 15 | 11 |
| File binari | slide, video, complementi, testo1 cap. 17 | 7 |
| Progettazione e implementazione di programmi C; ricerca e ordinamento | slide, EG, testo1 cap. 11-12, testo2 cap. 1-2 | 12, Laboratorio, Palestra |
| Metodologie di sviluppo e tecniche di test dei programmi | slide, video, testo2 cap. 1-2 | 13 |
| Strutture di dati astratte (ADT); tabelle (array di strutture) | slide, EG | 10 |
| Strutture dinamiche: liste concatenate | slide, EG, testo2 cap. 6 | 14 |
| Strutture dinamiche: alberi (cenni, quanto visto a lezione) | slide, EG, testo2 cap. 8 | 15 |

I capitoli 16-21 non aggiungono argomenti nuovi: servono a **prepararti alla prova** (metodo, tracce risolte e da svolgere, orale, formulario, palestra).

## Testi di riferimento

- **testo1**: A. Bellini, A. Guidi, *Linguaggio C*, McGraw-Hill. È il testo principale, nuovo da quest'anno: il professore preferisce che lo adottiate.
- **testo2**: D. Calvanese, P. Liberatore, F. Massacci, R. Rosati, *Programmazione di strutture dati in C*, Progetto Leonardo. Serve per **test**, **liste** (cap. 6) e **alberi** (cap. 8). Dalla lezione sulle liste in poi il corso lo usa "ufficialmente".
- In alternativa al testo1 si può usare il Deitel & Deitel (testo degli anni scorsi), seguendo le annotazioni del programma 2024/25.

Nel fascicolo, accanto a ogni capitolo, trovi tra parentesi i capitoli del testo indicati dal programma.

## Le date (A.A. 2026/27, dal sito del corso)

| Appello | Data e ora | Note |
|---|---|---|
| Gennaio | **22/01/2027**, ore 9:30, Aula 15 | il primo utile per te |
| Febbraio | **17/02/2027**, ore 9:30, Aula 15 | |
| Aprile (straordinario) | 09/04/2027, ore 15:30 | solo per categorie particolari (lavoratori, fuori corso, ...) |
| Giugno | 09/06/2027, ore 9:30, Aula 15 | |
| Luglio | 14/07/2027, ore 9:30, Aula 15 | |
| Settembre | 16/09/2027, ore 9:30 | aula da destinarsi |
| Ottobre (straordinario) | 29/10/2027, ore 15:30 | solo per categorie particolari |

Le date possono cambiare: controlla sempre la [pagina esami del corso](https://www.diag.uniroma1.it/marte/homepage/didattica/tdp-latina/tdp-esami.html) e Classroom.

## Come usare questo fascicolo

Prima di tutto leggi il [Laboratorio](#laboratorio): spiega come si **impara a programmare in C** davvero (ambiente, errori del compilatore, debugging, metodo). Alla fine del fascicolo c'è la [Palestra di programmazione](#palestra), con 25 esercizi graduati da fare al computer man mano che studi. Il fascicolo segue l'ordine del corso. Ogni capitolo ha spiegazioni semplici, codice C commentato e provato, riquadri colorati ed esercizi con soluzione nascosta (clicca su "Soluzione" solo dopo averci provato davvero).

::: esame All'esame
Questi riquadri dicono che cosa serve **proprio per lo scritto o l'orale**.
:::

::: errore Errore tipico
Questi riquadri mostrano gli sbagli che costano punti.
:::

::: nota Da sapere
Approfondimenti e collegamenti tra argomenti.
:::

### Un piano di studio consigliato (circa 8 settimane prima di gennaio)

| Settimana | Teoria | Pratica al computer |
|---|---|---|
| 1 | Laboratorio; architettura, rappresentazione dei numeri, basi del C | installa Dev-C++; Palestra livello 1 |
| 2 | Istruzioni di controllo, funzioni, record di attivazione | Palestra livelli 2 e 3 |
| 3 | Array, file, puntatori | Palestra livello 4; esercizi dei capitoli 6-8 |
| 4 | Stringhe, allocazione dinamica, struct e tabelle | Palestra livelli 5 e 6 |
| 5 | Ricorsione, ricerca e ordinamento, test | esercizi dei capitoli 11-13 |
| 6 | **Liste** (tutte le operazioni, a memoria e capite) | Palestra livello 7; esercizi del capitolo 14 |
| 7 | Alberi (cenni), metodo per lo scritto, tracce risolte | tracce del capitolo 17 rifatte da solo |
| 8 | Orale, formulario, autoverifica | tracce del capitolo 18 **su carta, a tempo** |

::: nota Il segreto per passare
Lo scritto premia chi ha **scritto a mano tante funzioni sulle liste**. Leggere le soluzioni non basta: prendi una traccia, chiudi il fascicolo, scrivi su carta in 2h30, poi correggi confrontando con le soluzioni e provando il codice al computer (Dev-C++, come al corso).
:::
