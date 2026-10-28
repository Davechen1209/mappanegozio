"""Importazione del catalogo da file CSV o Excel.

Non sappiamo ancora come sarà l'export del gestionale, quindi non diamo per
scontati i nomi delle colonne: è l'utente a dire quale colonna del file
corrisponde a quale campo (la "mappatura").
"""

import csv
import io
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

# I campi che possiamo riempire, con una descrizione per l'utente.
CAMPI = {
    "nome": "Nome del prodotto (obbligatorio)",
    "ean": "Codice EAN (codice a barre)",
    "codice_interno": "Codice interno del gestionale",
    "categoria": "Categoria o reparto merceologico",
    "sinonimi": "Altri nomi, separati da virgola",
    "foto_url": "Indirizzo della foto",
    "posizione": "Codice posizione, es. 11A (più posizioni separate da virgola o |)",
}

# Nomi di colonna frequenti: servono solo a suggerire una scelta all'utente.
SUGGERIMENTI = {
    "nome": ["nome", "descrizione", "articolo", "prodotto"],
    "ean": ["ean", "ean13", "barcode", "codice a barre"],
    "codice_interno": ["codice", "cod.art.", "cod art", "codice articolo", "sku"],
    "categoria": ["categoria", "famiglia", "reparto", "gruppo"],
    "sinonimi": ["sinonimi", "alias", "parole chiave"],
    "foto_url": ["foto", "immagine", "foto_url"],
    "posizione": ["posizione", "ubicazione", "scaffale", "collocazione"],
}


# ---------------------------------------------------------------- lettura file

def leggi_file(percorso):
    """Restituisce (intestazioni, righe) leggendo un .csv oppure un .xlsx."""
    percorso = Path(percorso)
    if percorso.suffix.lower() in (".xlsx", ".xlsm"):
        tabella = _leggi_excel(percorso)
    else:
        tabella = _leggi_csv(percorso)

    # Togliamo le righe completamente vuote.
    tabella = [riga for riga in tabella if any(cella.strip() for cella in riga)]
    if not tabella:
        raise ValueError(f"Il file {percorso.name} è vuoto")
    intestazioni = [cella.strip() for cella in tabella[0]]
    return intestazioni, tabella[1:]


def _leggi_csv(percorso):
    # I file salvati da Excel in Italia spesso non sono in UTF-8: proviamo entrambi.
    # latin-1 accetta qualsiasi byte, quindi è l'ultima spiaggia.
    for codifica in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            testo = percorso.read_text(encoding=codifica)
            break
        except UnicodeDecodeError:
            continue
    # Il separatore può essere ; (Excel italiano), virgola o tabulazione.
    try:
        dialetto = csv.Sniffer().sniff(testo[:5000], delimiters=";,\t")
    except csv.Error:
        dialetto = csv.excel  # file con una sola colonna: va bene la virgola
    return list(csv.reader(io.StringIO(testo), dialetto))


def _leggi_excel(percorso):
    import openpyxl  # lo importiamo solo se serve davvero

    foglio = openpyxl.load_workbook(percorso, read_only=True, data_only=True).active
    return [[_cella_in_testo(c) for c in riga] for riga in foglio.iter_rows(values_only=True)]


def _cella_in_testo(valore):
    if valore is None:
        return ""
    # Excel salva gli EAN come numeri: 8001234567890.0 deve tornare "8001234567890".
    if isinstance(valore, float) and valore.is_integer():
        return str(int(valore))
    return str(valore)


# ------------------------------------------------------------------ mappatura

def interpreta_mappatura(testo, intestazioni):
    """Legge una mappatura scritta come "nome=Descrizione,ean=EAN13".

    Restituisce un dizionario campo -> numero della colonna.
    """
    mappatura = {}
    for coppia in testo.split(","):
        campo, _, colonna = coppia.partition("=")
        campo, colonna = campo.strip(), colonna.strip()
        if campo not in CAMPI:
            raise ValueError(f"Campo sconosciuto: '{campo}'. Campi validi: {', '.join(CAMPI)}")
        mappatura[campo] = _trova_colonna(colonna, intestazioni)
    controlla_mappatura(mappatura)
    return mappatura


def _trova_colonna(nome, intestazioni):
    for i, intestazione in enumerate(intestazioni):
        if intestazione.lower() == nome.lower():
            return i
    raise ValueError(f"Colonna '{nome}' non trovata. Colonne del file: {', '.join(intestazioni)}")


def controlla_mappatura(mappatura):
    if "nome" not in mappatura:
        raise ValueError("Serve almeno la colonna del nome del prodotto")
    if "ean" not in mappatura and "codice_interno" not in mappatura:
        raise ValueError("Serve la colonna dell'EAN oppure quella del codice interno")


def suggerisci_colonna(campo, intestazioni):
    for i, intestazione in enumerate(intestazioni):
        if intestazione.lower() in SUGGERIMENTI[campo]:
            return i
    return None


def chiedi_mappatura(intestazioni, righe, chiedi=input):
    """Chiede all'utente, campo per campo, quale colonna usare."""
    print("\nColonne trovate nel file:")
    esempio = righe[0] if righe else []
    for i, intestazione in enumerate(intestazioni):
        valore = esempio[i] if i < len(esempio) else ""
        print(f"  {i + 1:>2}. {intestazione:<25} es. {valore}")

    print("\nPer ogni campo scrivi il numero della colonna, "
          "Invio per accettare il suggerimento, - per saltarlo.")
    mappatura = {}
    for campo, descrizione in CAMPI.items():
        suggerita = suggerisci_colonna(campo, intestazioni)
        proposta = str(suggerita + 1) if suggerita is not None else "-"
        risposta = chiedi(f"  {descrizione} [{proposta}]: ").strip() or proposta
        if risposta == "-":
            continue
        if not risposta.isdigit() or not 1 <= int(risposta) <= len(intestazioni):
            raise ValueError(f"'{risposta}' non è un numero di colonna valido")
        mappatura[campo] = int(risposta) - 1
    controlla_mappatura(mappatura)
    return mappatura


# --------------------------------------------------------------- importazione

@dataclass
class Risultato:
    nuovi: int = 0
    aggiornati: int = 0
    scartati: list = field(default_factory=list)              # (numero riga, motivo)
    posizioni_sconosciute: list = field(default_factory=list)  # (numero riga, codice)


def normalizza_posizione(testo):
    """ " 11 a " -> "11A" """
    return re.sub(r"\s+", "", testo).upper()


def importa_righe(conn, righe, mappatura):
    """Inserisce o aggiorna i prodotti. Ritorna un Risultato con il resoconto."""
    risultato = Risultato()
    codici_validi = {r["codice"]: r["id"] for r in conn.execute("SELECT codice, id FROM posizioni")}

    # La riga 1 del file è l'intestazione, quindi i dati partono dalla riga 2.
    for numero, riga in enumerate(righe, start=2):
        valori = {}
        for campo, colonna in mappatura.items():
            valore = riga[colonna].strip() if colonna < len(riga) else ""
            valori[campo] = valore or None

        if not valori["nome"]:
            risultato.scartati.append((numero, "manca il nome"))
            continue
        if not valori.get("ean") and not valori.get("codice_interno"):
            risultato.scartati.append((numero, "mancano sia EAN sia codice interno"))
            continue

        try:
            prodotto_id, nuovo = _salva_prodotto(conn, valori, mappatura)
        except sqlite3.IntegrityError as errore:
            risultato.scartati.append((numero, f"conflitto nel database: {errore}"))
            continue
        if nuovo:
            risultato.nuovi += 1
        else:
            risultato.aggiornati += 1

        if "posizione" in mappatura:
            _salva_posizioni(conn, prodotto_id, valori["posizione"], codici_validi,
                             numero, risultato)

    conn.commit()
    return risultato


def _salva_prodotto(conn, valori, mappatura):
    """Ritorna (id del prodotto, True se è nuovo)."""
    esistente = None
    if valori.get("ean"):
        esistente = conn.execute("SELECT id FROM prodotti WHERE ean = ?",
                                 (valori["ean"],)).fetchone()
    if esistente is None and valori.get("codice_interno"):
        esistente = conn.execute("SELECT id FROM prodotti WHERE codice_interno = ?",
                                 (valori["codice_interno"],)).fetchone()

    # Aggiorniamo solo i campi presenti nella mappatura, senza cancellare gli altri.
    campi = [c for c in mappatura if c != "posizione"]
    if esistente:
        assegnazioni = ", ".join(f"{c} = :{c}" for c in campi)
        conn.execute(f"UPDATE prodotti SET {assegnazioni} WHERE id = :id",
                     {**valori, "id": esistente["id"]})
        return esistente["id"], False

    colonne = ", ".join(campi)
    segnaposto = ", ".join(f":{c}" for c in campi)
    cursore = conn.execute(f"INSERT INTO prodotti ({colonne}) VALUES ({segnaposto})", valori)
    return cursore.lastrowid, True


def _salva_posizioni(conn, prodotto_id, testo, codici_validi, numero, risultato):
    # Il file è la fonte di verità: sostituiamo le posizioni del prodotto.
    conn.execute("DELETE FROM prodotto_posizioni WHERE prodotto_id = ?", (prodotto_id,))
    for pezzo in re.split(r"[,|]", testo or ""):
        codice = normalizza_posizione(pezzo)
        if not codice:
            continue
        if codice not in codici_validi:
            # Non inventiamo posizioni: le segnaliamo e basta.
            risultato.posizioni_sconosciute.append((numero, codice))
            continue
        conn.execute(
            "INSERT OR IGNORE INTO prodotto_posizioni (prodotto_id, posizione_id) VALUES (?, ?)",
            (prodotto_id, codici_validi[codice]),
        )
