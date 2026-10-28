"""Test del passo 1: database, configurazione e importazione.

Si lanciano con:  python -m pytest
"""

from pathlib import Path

import pytest

from negozio.configurazione import applica_configurazione, carica_configurazione
from negozio.db import connetti
from negozio.importa import chiedi_mappatura, importa_righe, interpreta_mappatura, leggi_file

DATI = Path(__file__).parent.parent / "dati_prova"
MAPPATURA_PROVA = ("codice_interno=Cod.Art.,nome=Descrizione,ean=EAN13,"
                   "categoria=Famiglia,posizione=Ubicazione,sinonimi=Sinonimi")


@pytest.fixture
def conn():
    """Un database nuovo, in memoria, con le posizioni del negozio di prova."""
    conn = connetti(":memory:")
    applica_configurazione(conn, carica_configurazione(DATI / "negozio.json"))
    yield conn
    conn.close()


def posizioni_di(conn, nome):
    righe = conn.execute("""
        SELECT pos.codice FROM posizioni pos
        JOIN prodotto_posizioni pp ON pp.posizione_id = pos.id
        JOIN prodotti p ON p.id = pp.prodotto_id
        WHERE p.nome = ? ORDER BY pos.codice
    """, (nome,))
    return [r["codice"] for r in righe]


def test_configurazione_crea_corsie_e_reparti(conn):
    # 20 corsie x 6 scaffali + 3 reparti
    assert conn.execute("SELECT COUNT(*) FROM posizioni").fetchone()[0] == 123
    scaffale = conn.execute("SELECT * FROM posizioni WHERE codice = '11C'").fetchone()
    assert scaffale["tipo"] == "scaffale" and scaffale["corsia"] == 11
    reparto = conn.execute("SELECT * FROM posizioni WHERE codice = 'FESTE'").fetchone()
    assert reparto["tipo"] == "reparto" and reparto["reparto"] == "Articoli per feste"


def test_configurazione_si_puo_rilanciare(conn):
    applica_configurazione(conn, carica_configurazione(DATI / "negozio.json"))
    assert conn.execute("SELECT COUNT(*) FROM posizioni").fetchone()[0] == 123


def test_importa_catalogo_di_prova(conn):
    intestazioni, righe = leggi_file(DATI / "catalogo_prova.csv")
    risultato = importa_righe(conn, righe, interpreta_mappatura(MAPPATURA_PROVA, intestazioni))

    assert risultato.nuovi == 52
    assert risultato.scartati == [] and risultato.posizioni_sconosciute == []
    # un prodotto con due posizioni
    assert posizioni_di(conn, "Candeline di compleanno 24 pezzi") == ["7D", "FESTE"]
    # uno scaffale con prodotti di tipo diverso
    categorie = conn.execute("""
        SELECT DISTINCT p.categoria FROM prodotti p
        JOIN prodotto_posizioni pp ON pp.prodotto_id = p.id
        JOIN posizioni pos ON pos.id = pp.posizione_id WHERE pos.codice = '11C'
    """).fetchall()
    assert len(categorie) > 1


def test_reimportare_aggiorna_senza_duplicare(conn):
    intestazioni, righe = leggi_file(DATI / "catalogo_prova.csv")
    mappatura = interpreta_mappatura(MAPPATURA_PROVA, intestazioni)
    importa_righe(conn, righe, mappatura)
    risultato = importa_righe(conn, righe, mappatura)
    assert risultato.nuovi == 0 and risultato.aggiornati == 52
    assert conn.execute("SELECT COUNT(*) FROM prodotti").fetchone()[0] == 52


def test_colonne_con_nomi_e_ordine_diversi(conn, tmp_path):
    # Un gestionale qualsiasi: separatore virgola, colonne in altro ordine, niente EAN.
    file = tmp_path / "export.csv"
    file.write_text("Ubicazione,Articolo,Codice\n 11 a ,Spugna,X1\n99Z,Secchio,X2\n,Senza codice,\n",
                    encoding="utf-8")
    intestazioni, righe = leggi_file(file)
    mappatura = interpreta_mappatura("nome=articolo,codice_interno=Codice,posizione=Ubicazione",
                                     intestazioni)
    risultato = importa_righe(conn, righe, mappatura)

    assert risultato.nuovi == 2
    assert posizioni_di(conn, "Spugna") == ["11A"]           # " 11 a " normalizzato
    assert risultato.posizioni_sconosciute == [(3, "99Z")]   # non viene inventata
    assert risultato.scartati == [(4, "mancano sia EAN sia codice interno")]


def test_importa_excel(conn, tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    libro = openpyxl.Workbook()
    libro.active.append(["EAN", "Descrizione", "Posizione"])
    libro.active.append([8001234567890, "Pellicola", "11C"])  # EAN salvato come numero
    file = tmp_path / "export.xlsx"
    libro.save(file)

    intestazioni, righe = leggi_file(file)
    importa_righe(conn, righe, interpreta_mappatura("ean=EAN,nome=Descrizione,posizione=Posizione",
                                                    intestazioni))
    prodotto = conn.execute("SELECT * FROM prodotti").fetchone()
    assert prodotto["ean"] == "8001234567890"


def test_mappatura_senza_nome_rifiutata():
    with pytest.raises(ValueError):
        interpreta_mappatura("ean=EAN", ["EAN", "Descrizione"])


def test_mappatura_interattiva_usa_i_suggerimenti(capsys):
    intestazioni, righe = leggi_file(DATI / "catalogo_prova.csv")
    # L'utente preme sempre Invio: accetta tutte le colonne suggerite.
    mappatura = chiedi_mappatura(intestazioni, righe, chiedi=lambda domanda: "")
    assert mappatura == {"nome": 1, "ean": 2, "codice_interno": 0, "categoria": 3,
                         "sinonimi": 5, "posizione": 4}
