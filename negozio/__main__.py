"""Comandi da terminale. Esempi:

    python -m negozio inizializza
    python -m negozio importa dati_prova/catalogo_prova.csv
    python -m negozio riepilogo
    python -m negozio scaffale 11A
"""

import argparse
import sys

from .configurazione import applica_configurazione, carica_configurazione
from .db import connetti
from .importa import chiedi_mappatura, importa_righe, interpreta_mappatura, leggi_file


def comando_inizializza(conn, argomenti):
    config = carica_configurazione(argomenti.config)
    quante = applica_configurazione(conn, config)
    print(f"Negozio '{config['nome']}': {quante} posizioni configurate.")


def comando_importa(conn, argomenti):
    intestazioni, righe = leggi_file(argomenti.file)
    if argomenti.colonne:
        mappatura = interpreta_mappatura(argomenti.colonne, intestazioni)
    else:
        mappatura = chiedi_mappatura(intestazioni, righe)

    risultato = importa_righe(conn, righe, mappatura)
    print(f"\nProdotti nuovi: {risultato.nuovi}, aggiornati: {risultato.aggiornati}, "
          f"righe scartate: {len(risultato.scartati)}")
    for numero, motivo in risultato.scartati:
        print(f"  riga {numero}: {motivo}")
    for numero, codice in risultato.posizioni_sconosciute:
        print(f"  riga {numero}: posizione '{codice}' non esiste nella configurazione")


def comando_riepilogo(conn, argomenti):
    conta = lambda sql: conn.execute(sql).fetchone()[0]
    print(f"Prodotti attivi:     {conta('SELECT COUNT(*) FROM prodotti WHERE attivo = 1')}")
    print(f"Posizioni:           {conta('SELECT COUNT(*) FROM posizioni')}")
    print(f"Posizioni occupate:  "
          f"{conta('SELECT COUNT(DISTINCT posizione_id) FROM prodotto_posizioni')}")

    senza = conn.execute("""
        SELECT nome FROM prodotti
        WHERE id NOT IN (SELECT prodotto_id FROM prodotto_posizioni)
        ORDER BY nome
    """).fetchall()
    if senza:
        print(f"\nProdotti senza posizione ({len(senza)}):")
        for riga in senza:
            print(f"  - {riga['nome']}")


def comando_scaffale(conn, argomenti):
    righe = conn.execute("""
        SELECT p.nome, p.categoria FROM prodotti p
        JOIN prodotto_posizioni pp ON pp.prodotto_id = p.id
        JOIN posizioni pos ON pos.id = pp.posizione_id
        WHERE pos.codice = ?
        ORDER BY p.nome
    """, (argomenti.codice.upper(),)).fetchall()
    if not righe:
        print(f"Nessun prodotto in {argomenti.codice.upper()}")
    for riga in righe:
        print(f"  {riga['nome']:<40} {riga['categoria'] or ''}")


def main():
    parser = argparse.ArgumentParser(prog="negozio", description="Assistente AI negozio")
    sotto = parser.add_subparsers(dest="comando", required=True)

    p = sotto.add_parser("inizializza", help="crea il database e le posizioni del negozio")
    p.add_argument("--config", default="dati_prova/negozio.json")
    p.set_defaults(funzione=comando_inizializza)

    p = sotto.add_parser("importa", help="importa un catalogo da CSV o Excel")
    p.add_argument("file")
    p.add_argument("--colonne", help='es. "nome=Descrizione,ean=EAN13,posizione=Ubicazione"')
    p.set_defaults(funzione=comando_importa)

    p = sotto.add_parser("riepilogo", help="mostra quanti prodotti e posizioni ci sono")
    p.set_defaults(funzione=comando_riepilogo)

    p = sotto.add_parser("scaffale", help="elenca i prodotti in una posizione")
    p.add_argument("codice")
    p.set_defaults(funzione=comando_scaffale)

    argomenti = parser.parse_args()
    conn = connetti()
    try:
        argomenti.funzione(conn, argomenti)
    except (ValueError, FileNotFoundError) as errore:
        sys.exit(f"Errore: {errore}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
