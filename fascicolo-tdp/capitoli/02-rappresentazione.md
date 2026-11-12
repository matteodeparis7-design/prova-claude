# Rappresentazione dell'informazione {#rappresentazione}

*(slide lezione 7, complementi "Sistemi di numerazione" e "Rappresentazione di numeri"; testo1 app. D)*

Nella memoria ci sono solo **bit** (0 e 1). Questo capitolo spiega come con i bit si rappresentano numeri interi, negativi e reali. Il **floating point** è uscito come **esercizio 3** in un testo d'esame: va saputo fare a mano, senza errori.

## Numeri e numerali

Un **numero** è un concetto; un **numerale** è la scrittura che lo rappresenta. Il numero dodici si scrive `12` in decimale, `XII` in cifre romane, `1100` in binario, `C` in esadecimale.

Nei **sistemi posizionali** ogni cifra "pesa" a seconda della posizione. In base *b*, il numerale c<sub>n-1</sub>...c<sub>1</sub>c<sub>0</sub> vale:

> c<sub>n-1</sub>·b<sup>n-1</sup> + ... + c<sub>1</sub>·b<sup>1</sup> + c<sub>0</sub>·b<sup>0</sup>

| Base | Cifre | Esempio |
|---|---|---|
| 2 (binario) | 0, 1 | `10011100`₂ = 128+16+8+4 = 156 |
| 8 (ottale) | 0...7 | `234`₈ = 2·64+3·8+4 = 156 |
| 10 (decimale) | 0...9 | 156 |
| 16 (esadecimale) | 0...9, A...F | `9C`₁₆ = 9·16+12 = 156 |

## Conversioni

### Da base 10 a base 2 (parte intera): divisioni successive

Dividi per 2, scrivi il resto, continua col quoziente finché arrivi a 0. Il numero binario sono i **resti letti dal basso verso l'alto**.

```text
156 : 2 = 78  resto 0   ^
 78 : 2 = 39  resto 0   |
 39 : 2 = 19  resto 1   |   leggo dal basso:
 19 : 2 =  9  resto 1   |   156 = 10011100 (base 2)
  9 : 2 =  4  resto 1   |
  4 : 2 =  2  resto 0   |
  2 : 2 =  1  resto 0   |
  1 : 2 =  0  resto 1   |
```

### Da base 2 a base 10: somma dei pesi

`10011100`₂: i pesi delle cifre 1 sono 128, 16, 8, 4, quindi 128 + 16 + 8 + 4 = **156**.

### Base 2, 8 e 16: a gruppi di bit

- in **ottale**, raggruppa i bit **a 3 a 3** partendo da destra: `10 011 100` = `2 3 4`₈;
- in **esadecimale**, raggruppa i bit **a 4 a 4**: `1001 1100` = `9 C`₁₆.

### Parte frazionaria: moltiplicazioni successive

Moltiplica la parte frazionaria per 2: la parte intera del risultato (0 o 1) è la prossima cifra; continua con la nuova parte frazionaria. Si legge **dall'alto verso il basso**.

```text
0.625 x 2 = 1.25  -> 1      leggo dall'alto:
0.25  x 2 = 0.5   -> 0      0.625 = 0.101 (base 2)
0.5   x 2 = 1.0   -> 1      (finisce: la parte frazionaria e` 0)
```

Molti numeri decimali "semplici" in binario sono **periodici** (infiniti): 0.1 = 0.000110011001100... Per questo `float` e `double` rappresentano molti reali **solo in modo approssimato**.

## Interi senza segno: binario puro

Con **n bit** si hanno 2<sup>n</sup> numerali, quindi si rappresentano i numeri da **0 a 2<sup>n</sup> - 1** (con 8 bit: da 0 a 255).

**Somma binaria**: come in decimale, con i riporti. 0+0=0, 0+1=1, 1+1=0 con riporto 1, 1+1+1=1 con riporto 1.

```text
  riporti:  1111111
            0001111001   (121)
          + 1001001111   (591)
          ------------
            1011001000   (712)
```

Se il risultato non sta negli n bit si ha **overflow**.

**Sottrazione binaria** (con il "prestito", come in decimale): 0-0=0, 1-0=1, 1-1=0, 0-1=1 **con prestito** di 1 dalla cifra a sinistra.

```text
    1 1 0 1 0     (26)         colonna per colonna, da destra:
  -   1 1 1 1     (15)         0-1: prendo in prestito -> 10-1 = 1
  -----------                  1-1 (meno il prestito) ... e cosi` via
    0 1 0 1 1     (11)         verifica: 26 - 15 = 11 = 01011   ok
```

Nei calcolatori però non si sottrae così: si **somma il complemento a due** del sottraendo (vedi sotto), così basta un solo circuito.

**Quanti bit servono al minimo?** Per un numero N ≥ 0 in binario puro serve il più piccolo n tale che 2<sup>n</sup> > N, cioè 2<sup>n</sup> - 1 ≥ N. Esempi: 121 < 128 = 2<sup>7</sup>, quindi **7 bit**; 591 < 1024 = 2<sup>10</sup> (e 591 > 511), quindi **10 bit**; 256 = 2<sup>8</sup> richiede **9 bit** (con 8 si arriva solo a 255). In complemento a due bisogna che il numero stia in [-2<sup>n-1</sup>, 2<sup>n-1</sup>-1]: per 121 servono 8 bit, per -591 ne servono 11.

## Interi con segno

### Modulo e segno

Il primo bit è il segno (0 = +, 1 = -), gli altri n-1 bit sono il valore assoluto. Intervallo: [-(2<sup>n-1</sup>-1), 2<sup>n-1</sup>-1]. Difetti: **due zeri** (`000` e `100` con 3 bit) e circuiti più complicati per i calcoli. Per questo non si usa.

### Complemento a due (quello vero)

Con n bit:

- se V ≥ 0: la rappresentazione è il binario puro di V su n bit;
- se V < 0: la rappresentazione è il binario puro di **2<sup>n</sup> + V** (cioè 2<sup>n</sup> - |V|).

Intervallo rappresentabile: **[-2<sup>n-1</sup>, 2<sup>n-1</sup> - 1]**. Con 8 bit: da -128 a +127. C'è un solo zero. Il primo bit vale 1 per tutti i negativi.

```text
n = 3:   000  001  010  011  100  101  110  111
          0    1    2    3   -4   -3   -2   -1
```

**Metodo pratico per un negativo**: scrivi |V| in binario su n bit, **inverti tutti i bit** (complemento a uno), **aggiungi 1**.

```text
-591 con 11 bit:   591       = 01001001111
                   invertito = 10110110000
                   +1        = 10110110001
verifica: 2^11 - 591 = 2048 - 591 = 1457 = 10110110001  ok
```

**Estensione del segno**: per scrivere lo stesso numero con più bit, si ripete a sinistra il primo bit. -1 è `111` su 3 bit, `1111` su 4, `11111111` su 8.

**Sottrazione = somma del negativo**: N - M = N + (-M), si sommano le rappresentazioni e si scarta l'eventuale riporto oltre l'ultimo bit.

**Overflow** in complemento a due: sommando due positivi si ottiene un "negativo" (o viceversa). Su 8 bit: 120 + 10 = 130, che non sta in [-128, 127]: `01111000 + 00001010 = 10000010`, che si legge -126.

::: esercizio Esercizio d'esame risolto (dal complemento didattico del professore)
N = 121, M = 591. (1) Numero minimo B di bit per scrivere N e M in binario puro. (2) Scriverli su B bit e calcolare N+M. (3) Numero minimo di bit per scrivere N e -M in complemento a due. (4) Calcolare N - M su 16 bit.
:::

::: soluzione
1. 121 = `1111001` (7 bit); 591 = `1001001111` (10 bit). Quindi **B = 10**.
2. N = `0001111001`, M = `1001001111`; la somma (vedi sopra) è `1011001000` = 512+128+64+8 = **712**. Ok.
3. N = 121 sta in [-2<sup>7</sup>, 2<sup>7</sup>-1] = [-128, 127], quindi gli bastano 8 bit; -591 richiede [-1024, 1023], cioè **11 bit**. Con 11 bit: N = `00001111001`, -M = `10110110001`.
4. Su 16 bit: N = `0000000001111001`, -M = `1111110110110001` (estensione del segno con 1). Somma: `1111111000101010`, che è -470 = 121 - 591. Verifica: 2<sup>16</sup> - 470 = 65066 = `1111111000101010`. Ok.
:::

## Numeri reali: il floating point a 32 bit

Viene dalla **notazione scientifica**: 223365000 = 2.23365 × 10<sup>8</sup>, con una **mantissa** (le cifre) e un **esponente** (l'ordine di grandezza). In binario si **normalizza** la mantissa nella forma **1.xxxx**.

Il `float` occupa **32 bit**:

```text
 | s |    E (8 bit)    |               M (23 bit)                 |
   1   esponente in       cifre della mantissa normalizzata
 segno eccesso 127        DOPO l'"1." (l'1 iniziale non si scrive)
```

Il numero rappresentato è: **(-1)<sup>s</sup> × 1.M × 2<sup>E - 127</sup>**

- **s**: 0 positivo, 1 negativo;
- **E**: l'esponente vero **più 127** (si dice "in eccesso 127"). Così E va da 0 a 255 e l'esponente vero può essere negativo;
- **M**: le cifre dopo la virgola della mantissa normalizzata, completate con zeri a destra fino a 23 bit.

### Procedura in 5 passi (da usare all'esame)

1. **Segno**: s = 0 se positivo, 1 se negativo. Da qui lavora col valore assoluto.
2. **Converti in binario** parte intera (divisioni) e parte frazionaria (moltiplicazioni).
3. **Normalizza**: sposta la virgola subito dopo il primo 1. Conta di quante posizioni l'hai spostata: è l'esponente **e** (positivo se l'hai spostata a sinistra, negativo se a destra).
4. **Esponente**: E = e + 127, scritto in binario su 8 bit.
5. **Mantissa**: M = le cifre dopo "1.", portate a 23 bit (zeri a destra se mancano; se avanzano, si **troncano**).

### Esempio: 4.25 (dalle slide)

4.25 = `100.01`₂ → normalizzato `1.0001` × 2<sup>2</sup> → E = 2 + 127 = 129 = `10000001`, M = `0001`.

```text
4.25  =  0 10000001 00010000000000000000000
```

### Esempio: 796.25 (dalle slide)

796 = `1100011100`, 0.25 = `.01` → `1100011100.01` = `1.10001110001` × 2<sup>9</sup>.
E = 9 + 127 = 136 = `10001000`; M = `10001110001` + zeri.

```text
796.25 = 0 10001000 10001110001000000000000
```

### Esempio inverso: da bit a numero

`1 10000000 10010010000000000000000`: s = 1 (negativo); E = 128, quindi e = 128 - 127 = 1; mantissa = 1.1001001 = 1 + 1/2 + 1/16 + 1/128 = 1.5703125. Numero = -1.5703125 × 2<sup>1</sup> = **-3.140625**.

::: esercizio Esercizio 3 d'esame: floating point di 1216.37
"Realizzare la rappresentazione in floating point su 32 bit del numero razionale 1216.37. Mostrare e descrivere accuratamente i passaggi."
:::

::: soluzione
**1. Segno**: positivo, s = `0`.

**2a. Parte intera** 1216 (divisioni per 2):

```text
1216:2=608 r0   608:2=304 r0   304:2=152 r0   152:2=76 r0
  76:2= 38 r0    38:2= 19 r0    19:2=  9 r1     9:2= 4 r1
   4:2=  2 r0     2:2=  1 r0     1:2=  0 r1
letti dal basso:  1216 = 10011000000   (11 cifre; verifica: 1024+128+64 = 1216)
```

**2b. Parte frazionaria** 0.37 (moltiplicazioni per 2). Ci servono abbastanza cifre: la mantissa ha 23 bit, 10 vanno alla parte intera (le cifre dopo il primo 1), quindi ne servono **13** della parte frazionaria (più una per controllo):

```text
0.37x2=0.74 ->0   0.74x2=1.48 ->1   0.48x2=0.96 ->0   0.96x2=1.92 ->1
0.92x2=1.84 ->1   0.84x2=1.68 ->1   0.68x2=1.36 ->1   0.36x2=0.72 ->0
0.72x2=1.44 ->1   0.44x2=0.88 ->0   0.88x2=1.76 ->1   0.76x2=1.52 ->1
0.52x2=1.04 ->1   0.04x2=0.08 ->0   ...  (non finisce mai: e` periodico)
0.37 = 0.0101111010111 0...  (base 2)
```

Quindi 1216.37 ≈ `10011000000.0101111010111`

**3. Normalizzo**: sposto la virgola di **10** posizioni a sinistra, subito dopo il primo 1:
`1.00110000000101111010111` × 2<sup>10</sup>

**4. Esponente**: E = 10 + 127 = 137 = `10001001`

**5. Mantissa**: le 23 cifre dopo "1.": `0011000000` (10 cifre dalla parte intera) + `0101111010111` (13 cifre dalla frazione) = `00110000000101111010111`

```text
1216.37  =  0 10001001 00110000000101111010111
```

**Osservazione da scrivere**: la parte frazionaria è periodica, quindi la rappresentazione è **approssimata**; le cifre oltre la 23esima vanno perse (il valore memorizzato è circa 1216.36999512). La cifra successiva era 0, quindi troncare o arrotondare dà lo stesso risultato. Verifica: `1.0011` × 2<sup>10</sup> = `10011000000` = 1216. Ok.
:::

::: esercizio Esercizio 2.2
Rappresenta in floating point a 32 bit: (a) 5.375, (b) -45.625. Poi (c) calcola il numero rappresentato da `1 10000100 01101101000000000000000`.
:::

::: soluzione
(a) 5.375 = `101.011` = `1.01011` × 2<sup>2</sup>; E = 129 = `10000001` → `0 10000001 01011000000000000000000`.

(b) 45 = `101101`, 0.625 = `.101` → `101101.101` = `1.01101101` × 2<sup>5</sup>; s = 1, E = 132 = `10000100` → `1 10000100 01101101000000000000000`.

(c) È proprio il risultato di (b): s = 1, E = 132 → e = 5, mantissa `1.01101101`, quindi `-101101.101` = **-45.625**.
:::

## Caratteri

Anche i caratteri sono numeri: ogni carattere ha un **codice** nella tabella **ASCII** (7 bit, di solito in un byte). In C il tipo `char` è un piccolo intero.

| Carattere | Codice | Carattere | Codice |
|---|---|---|---|
| `'0'` ... `'9'` | 48 ... 57 | `'a'` ... `'z'` | 97 ... 122 |
| `'A'` ... `'Z'` | 65 ... 90 | `' '` (spazio) | 32 |
| `'\0'` (fine stringa) | 0 | `'\n'` (a capo) | 10 |

Conseguenze utili: `'7' - '0'` vale 7 (da carattere cifra a numero); `'a' - 'A'` vale 32 (da maiuscola a minuscola basta sommare 32); le lettere sono consecutive, quindi `c >= 'a' && c <= 'z'` controlla se `c` è minuscola.

::: esame All'orale
Sappi spiegare **perché** si usa il complemento a due (un solo zero, la sottrazione diventa una somma), **perché** i float sono approssimati (numero finito di bit, frazioni periodiche) e perché l'esponente è in eccesso 127 (per avere esponenti negativi senza un bit di segno in più).
:::
