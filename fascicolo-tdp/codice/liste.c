/* liste.c - Libreria di base per liste collegate (semplicemente concatenate)
   di interi, nello stile del corso (e del testo Calvanese et al.).
   Compilare con:  gcc -std=c89 -pedantic -Wall liste.c -o liste          */

#include <stdio.h>
#include <stdlib.h>

/* >>> tipi */
typedef int TipoInfo;              /* il tipo dell'informazione nel nodo */

struct nodo {
  TipoInfo info;                   /* il dato                            */
  struct nodo *next;               /* puntatore al nodo successivo       */
};

typedef struct nodo TipoNodo;      /* un nodo (record)                   */
typedef TipoNodo *TipoLista;       /* una lista = puntatore al 1o nodo   */
/* <<< tipi */

/* prototipi */
void stampaLista(TipoLista l);
int lunghezza(TipoLista l);
TipoNodo *cerca(TipoLista l, TipoInfo x);
int insTesta(TipoLista *pl, TipoInfo x);
int insCoda(TipoLista *pl, TipoInfo x);
int insCodaRG(TipoLista *pl, TipoInfo x);
int insOrdinato(TipoLista *pl, TipoInfo x);
int elimina(TipoLista *pl, TipoInfo x);
void dealloca(TipoLista *pl);
int lunghezzaRic(TipoLista l);
int contaRic(TipoLista l, TipoInfo x);
void stampaInversaRic(TipoLista l);
int maxLista(TipoLista l, int *pmax);

/* >>> stampa */
void stampaLista(TipoLista l) {
  TipoNodo *p = l;           /* p "scorre" la lista, l resta fermo */
  while (p != NULL) {
    printf("%d -> ", p->info);
    p = p->next;             /* avanzamento al nodo successivo     */
  }
  printf("NULL\n");
}
/* <<< stampa */

/* >>> lunghezza */
int lunghezza(TipoLista l) {
  int n = 0;
  while (l != NULL) {        /* l e` una COPIA: possiamo muoverla  */
    n++;
    l = l->next;
  }
  return n;
}
/* <<< lunghezza */

/* >>> cerca */
/* restituisce il puntatore al primo nodo che contiene x, NULL se non c'e` */
TipoNodo *cerca(TipoLista l, TipoInfo x) {
  while (l != NULL && l->info != x)   /* l'ordine delle condizioni conta! */
    l = l->next;
  return l;
}
/* <<< cerca */

/* >>> insTesta */
/* inserimento in testa: la testa cambia, quindi serve TipoLista *
   restituisce 1 se l'inserimento riesce, 0 se la malloc fallisce       */
int insTesta(TipoLista *pl, TipoInfo x) {
  TipoNodo *nuovo = malloc(sizeof(TipoNodo));   /* 1. alloco          */
  if (nuovo == NULL)
    return 0;
  nuovo->info = x;                               /* 2. riempio         */
  nuovo->next = *pl;                             /* 3. aggancio        */
  *pl = nuovo;                                   /* 4. nuova testa     */
  return 1;
}
/* <<< insTesta */

/* >>> insCoda */
/* inserimento in coda, versione "con caso speciale" per la lista vuota */
int insCoda(TipoLista *pl, TipoInfo x) {
  TipoNodo *nuovo, *p;
  nuovo = malloc(sizeof(TipoNodo));
  if (nuovo == NULL)
    return 0;
  nuovo->info = x;
  nuovo->next = NULL;              /* sara` l'ultimo                    */
  if (*pl == NULL)                 /* caso speciale: lista vuota        */
    *pl = nuovo;
  else {
    p = *pl;
    while (p->next != NULL)        /* mi fermo sull'ULTIMO nodo         */
      p = p->next;
    p->next = nuovo;
  }
  return 1;
}
/* <<< insCoda */

/* >>> insCodaRG */
/* inserimento in coda con la tecnica del RECORD GENERATORE (RG):
   un nodo fittizio messo in testa elimina il caso speciale             */
int insCodaRG(TipoLista *pl, TipoInfo x) {
  TipoNodo rg;                     /* record generatore (variabile locale) */
  TipoNodo *p, *nuovo;
  nuovo = malloc(sizeof(TipoNodo));
  if (nuovo == NULL)
    return 0;
  nuovo->info = x;
  nuovo->next = NULL;
  rg.next = *pl;                   /* RG davanti al primo nodo vero     */
  p = &rg;                         /* p parte dal RG: non e` mai NULL   */
  while (p->next != NULL)
    p = p->next;
  p->next = nuovo;                 /* se la lista era vuota, p == &rg   */
  *pl = rg.next;                   /* la testa vera e` dopo il RG       */
  return 1;
}
/* <<< insCodaRG */

/* >>> insOrdinato */
/* inserimento che mantiene la lista ordinata in modo CRESCENTE */
int insOrdinato(TipoLista *pl, TipoInfo x) {
  TipoNodo *nuovo, *prec, *corr;
  nuovo = malloc(sizeof(TipoNodo));
  if (nuovo == NULL)
    return 0;
  nuovo->info = x;
  prec = NULL;                     /* nodo che precede corr             */
  corr = *pl;
  while (corr != NULL && corr->info < x) {  /* cerco il punto giusto    */
    prec = corr;
    corr = corr->next;
  }
  nuovo->next = corr;              /* il nuovo nodo precede corr        */
  if (prec == NULL)                /* va in testa (lista vuota o x min) */
    *pl = nuovo;
  else
    prec->next = nuovo;
  return 1;
}
/* <<< insOrdinato */

/* >>> elimina */
/* elimina il PRIMO nodo che contiene x; restituisce 1 se eliminato, 0 se assente */
int elimina(TipoLista *pl, TipoInfo x) {
  TipoNodo *prec = NULL, *corr = *pl;
  while (corr != NULL && corr->info != x) {
    prec = corr;
    corr = corr->next;
  }
  if (corr == NULL)                /* x non trovato                     */
    return 0;
  if (prec == NULL)                /* era il primo nodo: cambia la testa */
    *pl = corr->next;
  else
    prec->next = corr->next;       /* "scavalco" corr                   */
  free(corr);                      /* restituisco la memoria            */
  return 1;
}
/* <<< elimina */

/* >>> dealloca */
void dealloca(TipoLista *pl) {
  TipoNodo *daLiberare;
  while (*pl != NULL) {
    daLiberare = *pl;
    *pl = (*pl)->next;             /* prima avanzo ...                  */
    free(daLiberare);              /* ... poi libero (mai il contrario!) */
  }
}
/* <<< dealloca */

/* >>> ricorsive */
/* una lista e` VUOTA oppure e` un NODO seguito da una LISTA:
   e` una struttura intrinsecamente ricorsiva                           */
int lunghezzaRic(TipoLista l) {
  if (l == NULL)                       /* caso base: lista vuota        */
    return 0;
  return 1 + lunghezzaRic(l->next);    /* 1 (questo nodo) + resto       */
}

int contaRic(TipoLista l, TipoInfo x) {
  if (l == NULL)
    return 0;
  if (l->info == x)
    return 1 + contaRic(l->next, x);
  return contaRic(l->next, x);
}

void stampaInversaRic(TipoLista l) {
  if (l != NULL) {
    stampaInversaRic(l->next);         /* prima il resto (al contrario) */
    printf("%d ", l->info);            /* poi questo nodo               */
  }
}
/* <<< ricorsive */

/* >>> maxLista */
/* parametro di output: il massimo va in *pmax; il valore restituito
   dice se il massimo esiste (lista non vuota)                          */
int maxLista(TipoLista l, int *pmax) {
  if (l == NULL)
    return 0;
  *pmax = l->info;
  for (l = l->next; l != NULL; l = l->next)
    if (l->info > *pmax)
      *pmax = l->info;
  return 1;
}
/* <<< maxLista */

/* >>> main */
int main(void) {
  TipoLista l = NULL;              /* SEMPRE inizializzare a NULL!      */
  int i, m;

  for (i = 1; i <= 3; i++)
    insTesta(&l, i);               /* passo l'INDIRIZZO di l            */
  stampaLista(l);                  /* 3 -> 2 -> 1 -> NULL               */

  insCoda(&l, 10);
  insCodaRG(&l, 20);
  stampaLista(l);                  /* 3 -> 2 -> 1 -> 10 -> 20 -> NULL   */
  printf("lunghezza: %d (ricorsiva: %d)\n", lunghezza(l), lunghezzaRic(l));

  elimina(&l, 3);                  /* elimino il primo nodo             */
  elimina(&l, 10);                 /* elimino un nodo in mezzo          */
  elimina(&l, 99);                 /* non c'e`: restituisce 0           */
  stampaLista(l);                  /* 2 -> 1 -> 20 -> NULL              */

  if (maxLista(l, &m))
    printf("massimo: %d\n", m);
  printf("contrario: ");
  stampaInversaRic(l);
  printf("\n");
  dealloca(&l);

  insOrdinato(&l, 5); insOrdinato(&l, 1); insOrdinato(&l, 9);
  insOrdinato(&l, 7); insOrdinato(&l, 1);
  stampaLista(l);                  /* 1 -> 1 -> 5 -> 7 -> 9 -> NULL     */
  printf("quanti 1: %d\n", contaRic(l, 1));
  printf("cerco 7: %s\n", cerca(l, 7) != NULL ? "trovato" : "assente");
  dealloca(&l);
  printf("dopo dealloca: ");
  stampaLista(l);                  /* NULL                              */
  return 0;
}
/* <<< main */
