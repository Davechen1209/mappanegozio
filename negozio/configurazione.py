"""Configurazione del negozio: corsie, scaffali e reparti.

Ogni negozio ha il suo file JSON (vedi dati_prova/negozio.json).
Da quel file creiamo le righe della tabella `posizioni`, con le coordinate
x/y che serviranno per evidenziare il punto sulla piantina.
"""

import json

# Spazio lasciato libero ai bordi della piantina e sotto le corsie (per i reparti).
MARGINE = 40
SPAZIO_REPARTI = 160


def carica_configurazione(percorso):
    with open(percorso, encoding="utf-8") as f:
        return json.load(f)


def calcola_posizioni(config):
    """Restituisce la lista di tutte le posizioni del negozio, come dizionari."""
    larghezza = config["piantina"]["larghezza"]
    altezza = config["piantina"]["altezza"]
    numero_corsie = config["corsie"]["numero"]
    lettere = config["corsie"]["scaffali"]

    # Le corsie sono colonne una accanto all'altra; gli scaffali scendono dall'alto.
    passo_x = (larghezza - 2 * MARGINE) / numero_corsie
    passo_y = (altezza - 2 * MARGINE - SPAZIO_REPARTI) / len(lettere)

    posizioni = []
    for corsia in range(1, numero_corsie + 1):
        for i, lettera in enumerate(lettere):
            posizioni.append({
                "codice": f"{corsia}{lettera}",
                "tipo": "scaffale",
                "corsia": corsia,
                "reparto": None,
                "x": round(MARGINE + (corsia - 0.5) * passo_x, 1),
                "y": round(MARGINE + (i + 0.5) * passo_y, 1),
            })

    for reparto in config["reparti"]:
        posizioni.append({
            "codice": reparto["codice"],
            "tipo": "reparto",
            "corsia": None,
            "reparto": reparto["nome"],
            "x": reparto["x"],
            "y": reparto["y"],
        })
    return posizioni


def applica_configurazione(conn, config):
    """Scrive le posizioni nel database. Si può rilanciare: aggiorna quelle esistenti."""
    posizioni = calcola_posizioni(config)
    conn.executemany(
        """
        INSERT INTO posizioni (codice, tipo, corsia, reparto, x, y)
        VALUES (:codice, :tipo, :corsia, :reparto, :x, :y)
        ON CONFLICT (codice) DO UPDATE SET
            tipo = excluded.tipo, corsia = excluded.corsia,
            reparto = excluded.reparto, x = excluded.x, y = excluded.y
        """,
        posizioni,
    )
    conn.commit()
    return len(posizioni)
