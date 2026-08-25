# Assistente Asta - Fantacalcio Mantra (web)

Versione web dello strumento `Asta_Mantra.xlsm`. La logica VBA e' stata riscritta
in Python: backend di calcolo + frontend Streamlit, così funziona online per tutta
la lega senza Excel.

## Componenti

- `fanta_engine.py` — motore di calcolo (nessuna dipendenza da Streamlit):
  caricamento dati dal workbook, ottimizzatore di formazione (`solve_slots`, DP su
  bitmask, porting di `RisolviSlot`), classifica moduli, formazione tipo, scarsita'.
- `data_store.py` — registro acquisti condiviso (SQLite) + validazione acquisti
  (porting di `SvuotaInserimento`).
- `app.py` — interfaccia Streamlit (Dashboard, Registra acquisto, Campetto, Listone).
- `Asta_Mantra.xlsm` — sorgente dei dati di riferimento (Listone / Moduli / Squadre).

## Avvio locale

```bash
pip install -r requirements.txt
streamlit run app.py
```

Nome lega richiesto all'avvio: **Mantra Dei Forti**.

## Test

```bash
python -m pytest tests/ -q
```

## Dati e persistenza

- **Listone / Moduli / Squadre**: letti in sola lettura da `Asta_Mantra.xlsm`
  (le colonne dei rating per ruolo sono `Rt_Por … Rt_Pc`, un rating vuoto significa
  "ruolo non coperto").
- **Registro acquisti**: unico dato scrivibile, salvato in `acquisti.db` (SQLite).

> Nota deploy: su Streamlit Community Cloud il filesystem è effimero (si azzera ai
> redeploy/stop). Per un'asta condivisa realmente persistente, implementare
> l'interfaccia `PurchaseStore` di `data_store.py` con un backend esterno
> (Google Sheets o Supabase/Postgres) e usarlo al posto di `SQLitePurchaseStore`.

## Deploy (Streamlit Community Cloud)

1. Pubblica la cartella su un repository GitHub (incluso `Asta_Mantra.xlsm`).
2. Crea una app su https://share.streamlit.io puntando a `app.py`.
3. Per un backend di persistenza esterno, inserisci le credenziali nei *Secrets*.

## Regole implementate (dalla macro)

- 500 crediti, minimo 3 portieri, rosa max 80.
- Un giocatore copre uno slot solo se il ruolo è tra i suoi ruoli nativi
  (nessun adattamento).
- L'ottimizzatore massimizza prima la **copertura** degli slot (bonus interno) e poi
  la somma dei rating; il totale mostrato esclude il bonus.
- Classifica moduli ordinata per totale decrescente, poi per slot scoperti crescenti.
