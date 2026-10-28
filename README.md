# Assistente AI negozio

Tablet al centro del negozio che dice al cliente, in qualsiasi lingua, su quale
scaffale si trova un prodotto. Negozio pilota: **FULL – Tutto a meno**.

## Stato dei lavori

| Passo | Cosa | Stato |
|---|---|---|
| 1 | Database e importazione del catalogo | ✅ fatto |
| 2 | Ricerca AI testuale | da fare |
| 3 | Schermata cliente con piantina | da fare |
| 4 | Voce e lingue | da fare |
| 5 | Segnalazioni e prodotti mancanti | da fare |
| 6 | Pannello staff con PIN | da fare |
| 7 | Installazione sul tablet | da fare |

## Come provarlo

Serve Python 3.10 o più recente.

```bash
pip install -r requirements.txt

python -m negozio inizializza      # crea negozio.db con corsie, scaffali e reparti
python -m negozio importa dati_prova/catalogo_prova.csv   # chiede quale colonna è quale
python -m negozio riepilogo        # quanti prodotti, quali senza posizione
python -m negozio scaffale 11C     # cosa c'è sullo scaffale 11C

python -m pytest                   # lancia i test automatici
```

Per importare senza domande (utile quando il formato del gestionale sarà noto):

```bash
python -m negozio importa catalogo.xlsx \
  --colonne "nome=Descrizione,ean=EAN13,codice_interno=Cod.Art.,posizione=Ubicazione"
```

## Come è organizzato il codice

```
negozio/
  db.py              le 5 tabelle (prodotti, posizioni, prodotto_posizioni, richieste, segnalazioni)
  configurazione.py  dal file JSON del negozio alle posizioni con coordinate sulla piantina
  importa.py         lettura CSV/Excel, scelta delle colonne, inserimento dei prodotti
  __main__.py        i comandi da terminale
dati_prova/
  negozio.json       20 corsie con scaffali A–F e 3 macro reparti
  catalogo_prova.csv 52 prodotti inventati (EAN di prova che iniziano con 200)
tests/               verificano che tutto funzioni
```

### Scelte da sapere

- **Ogni negozio ha il suo `negozio.json`**: numero di corsie, lettere degli scaffali e
  reparti con la loro posizione sulla piantina.
- **I prodotti hanno un `id` numerico** come chiave interna: alcuni articoli non hanno
  l'EAN, quindi un prodotto si riconosce dall'EAN se c'è, altrimenti dal codice interno.
- **Le posizioni sconosciute non vengono inventate**: se il file dice `99Z` e quello
  scaffale non esiste nella configurazione, l'importazione lo segnala.
- **Reimportare è sicuro**: i prodotti già presenti vengono aggiornati, non duplicati.
