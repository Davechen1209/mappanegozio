"""Database del negozio: creazione delle tabelle e connessione.

Usiamo SQLite, un database che vive in un unico file (es. negozio.db).
Non serve installare nessun server: è già incluso in Python.
"""

import os
import sqlite3

# Il percorso del file si può cambiare con la variabile d'ambiente NEGOZIO_DB.
PERCORSO_PREDEFINITO = "negozio.db"

# Lo schema: le cinque tabelle descritte nel documento di progetto.
SCHEMA = """
CREATE TABLE IF NOT EXISTS prodotti (
    id              INTEGER PRIMARY KEY,
    ean             TEXT UNIQUE,
    codice_interno  TEXT UNIQUE,
    nome            TEXT NOT NULL,
    categoria       TEXT,
    sinonimi        TEXT,              -- parole separate da virgola
    foto_url        TEXT,
    attivo          INTEGER NOT NULL DEFAULT 1,
    -- ogni prodotto deve avere almeno uno dei due codici
    CHECK (ean IS NOT NULL OR codice_interno IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS posizioni (
    id       INTEGER PRIMARY KEY,
    codice   TEXT NOT NULL UNIQUE,     -- es. 11A oppure FESTE
    tipo     TEXT NOT NULL CHECK (tipo IN ('scaffale', 'reparto')),
    corsia   INTEGER,                  -- solo per gli scaffali
    reparto  TEXT,                     -- nome leggibile, solo per i reparti
    x        REAL,                     -- coordinate sulla piantina
    y        REAL
);

CREATE TABLE IF NOT EXISTS prodotto_posizioni (
    prodotto_id   INTEGER NOT NULL REFERENCES prodotti(id) ON DELETE CASCADE,
    posizione_id  INTEGER NOT NULL REFERENCES posizioni(id) ON DELETE CASCADE,
    PRIMARY KEY (prodotto_id, posizione_id)
);

CREATE TABLE IF NOT EXISTS richieste (
    id                   INTEGER PRIMARY KEY,
    testo                TEXT NOT NULL,
    lingua               TEXT,
    prodotti_mostrati    TEXT,         -- lista di id in formato JSON
    trovato_in_catalogo  INTEGER NOT NULL DEFAULT 0,
    gruppo_mancante      TEXT,
    data_ora             TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS segnalazioni (
    id                  INTEGER PRIMARY KEY,
    prodotto_id         INTEGER REFERENCES prodotti(id) ON DELETE SET NULL,
    posizione_mostrata  TEXT,
    data_ora            TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    stato               TEXT NOT NULL DEFAULT 'aperta'
                        CHECK (stato IN ('aperta', 'controllata'))
);
"""


def connetti(percorso=None):
    """Apre il database (lo crea se non esiste) e si assicura che le tabelle ci siano."""
    percorso = percorso or os.environ.get("NEGOZIO_DB", PERCORSO_PREDEFINITO)
    conn = sqlite3.connect(percorso)
    # Così le righe si leggono per nome: riga["nome"] invece di riga[3].
    conn.row_factory = sqlite3.Row
    # SQLite controlla i collegamenti tra tabelle solo se glielo chiediamo.
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn
