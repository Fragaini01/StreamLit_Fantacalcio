"""Assistente Asta - Fantacalcio Mantra (frontend Streamlit).

Porta online la logica del file Asta_Mantra.xlsm: registro acquisti condiviso,
classifica dei moduli, formazione tipo, scarsita' per ruolo e campetto.
Il motore di calcolo e' in fanta_engine.py, la persistenza in data_store.py.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import streamlit as st

import fanta_engine as fe
from data_store import SQLitePurchaseStore, ValidationError, validate_and_add

LEGA_NAME = "Mantra Dei Forti"
WORKBOOK = "Asta_Mantra.xlsm"

st.set_page_config(page_title="Assistente Asta - Mantra", layout="wide")


# ----------------------------------------------------------------------------
# Risorse condivise (cache)
# ----------------------------------------------------------------------------
@st.cache_resource
def get_reference() -> fe.ReferenceData:
    return fe.load_reference(WORKBOOK)


@st.cache_resource
def get_store() -> SQLitePurchaseStore:
    return SQLitePurchaseStore("acquisti.db")


def purchases_as_dicts(store: SQLitePurchaseStore) -> list[dict]:
    return [
        {"nome": p.nome, "squadra": p.squadra, "costo": p.costo}
        for p in store.list_purchases()
    ]


# ----------------------------------------------------------------------------
# Gate nome lega
# ----------------------------------------------------------------------------
def lega_gate() -> bool:
    if st.session_state.get("lega_ok"):
        return True
    st.title("Benvenuto!")
    lega_input = st.text_input("Inserisci il nome della lega per continuare:")
    if st.button("Avanti"):
        if lega_input == LEGA_NAME:
            st.session_state["lega_ok"] = True
            st.rerun()
        else:
            st.error("Nome lega non corretto. Riprova.")
    return False


# ----------------------------------------------------------------------------
# Campetto (matplotlib)
# ----------------------------------------------------------------------------
def _pitch_positions(module_name: str) -> list[tuple[float, float]]:
    """Coordinate (x, y) per gli 11 slot: slot 0 = portiere in basso, poi linee verso l'alto."""
    digits = [int(d) for d in module_name.split("-") if d.isdigit()]
    n_lines = len(digits)
    positions: list[tuple[float, float]] = [(5.0, 0.5)]  # portiere
    for li, count in enumerate(digits):
        y = 2.0 + li * (8.0 / max(n_lines, 1))
        for k in range(count):
            x = (k + 1) * (10.0 / (count + 1))
            positions.append((x, y))
    return positions


def draw_pitch(pitch: list[fe.PitchSlot], module_name: str):
    fig, ax = plt.subplots(figsize=(8, 10))
    ax.set_facecolor("#2e8b57")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 11)
    ax.set_xticks([])
    ax.set_yticks([])
    # linee campo
    ax.plot([0.3, 9.7, 9.7, 0.3, 0.3], [0.2, 0.2, 10.8, 10.8, 0.2], color="white", lw=2)
    ax.plot([0.3, 9.7], [5.5, 5.5], color="white", lw=1)

    positions = _pitch_positions(module_name)
    for slot, (x, y) in zip(pitch, positions):
        covered = slot.starter_name is not None
        ax.plot(x, y, "o", markersize=34, color="#d62728" if covered else "#888888",
                markeredgecolor="white", markeredgewidth=1.5, zorder=3)
        if covered:
            ax.text(x, y + 0.45, slot.starter_name, ha="center", va="bottom",
                    fontsize=9, fontweight="bold", color="white", zorder=4)
            label = f"{slot.starter_role} {slot.starter_points:.1f}"
        else:
            label = slot.slot_text
        ax.text(x, y - 0.55, label, ha="center", va="top", fontsize=8, color="white", zorder=4)
        if slot.subs:
            subs_txt = "\n".join(f"{n} ({r:.1f})" for n, r in slot.subs)
            ax.text(x, y - 0.95, subs_txt, ha="center", va="top", fontsize=6,
                    color="#e0e0e0", zorder=4)

    ax.set_title(f"Modulo {module_name}", color="black", fontsize=14, fontweight="bold")
    fig.tight_layout()
    return fig


# ----------------------------------------------------------------------------
# Pagine
# ----------------------------------------------------------------------------
def page_registra(ref: fe.ReferenceData, store: SQLitePurchaseStore, my_team: str):
    st.header("Registra un acquisto")
    with st.form("registra", clear_on_submit=True):
        col1, col2, col3 = st.columns([3, 2, 1])
        nome = col1.text_input("Giocatore")
        squadra = col2.selectbox("Squadra", ref.teams, index=ref.teams.index(my_team))
        costo = col3.number_input("Costo", min_value=0, max_value=fe.CREDITI, value=1, step=1)
        submitted = st.form_submit_button("Registra")
    if submitted:
        try:
            p = validate_and_add(store, ref, nome, squadra, costo)
            st.success(f"Registrato: {p.nome} -> {p.squadra} ({int(p.costo)})")
        except ValidationError as exc:
            st.error(str(exc))
            simili = [
                pl.nome for pl in ref.players if nome and nome.lower() in pl.nome.lower()
            ][:8]
            if simili:
                st.info("Nomi simili: " + ", ".join(simili))

    st.subheader("Acquisti registrati in lega")
    purchases = store.list_purchases()
    if not purchases:
        st.info("Nessun acquisto registrato.")
        return
    for p in purchases:
        c1, c2, c3, c4 = st.columns([3, 2, 1, 1])
        c1.write(p.nome)
        c2.write(p.squadra)
        c3.write(int(p.costo))
        if c4.button("Rimuovi", key=f"del_{p.id}"):
            store.remove_purchase(p.id)
            st.rerun()


def page_dashboard(ref: fe.ReferenceData, store: SQLitePurchaseStore, my_team: str):
    st.header(f"Dashboard - {my_team}")
    res = fe.compute_dashboard(ref, purchases_as_dicts(store), my_team)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Crediti residui", f"{int(res.credits_left)}/{fe.CREDITI}")
    m2.metric("Giocatori in rosa", res.rosa_size)
    m3.metric("Portieri", res.portieri)
    m4.metric("Acquisti in lega", res.n_acq)

    if res.messages:
        with st.container(border=True):
            for msg in res.messages:
                st.write("- " + msg)

    if not res.module_ranking:
        return

    st.subheader("Classifica moduli")
    st.dataframe(
        [
            {
                "Modulo": m.nome,
                "Totale": m.total,
                "Media": round(m.total / fe.NSLOT, 2),
                "Coperti": m.covered,
                "Scoperti": m.uncovered,
            }
            for m in res.module_ranking
        ],
        hide_index=True,
        use_container_width=True,
    )

    st.subheader(f"Formazione tipo - {res.best_module}  (totale {res.formation_total:.2f})")
    st.dataframe(
        [
            {
                "Slot": f.slot_text,
                "Giocatore": f.player_name or "(scoperto)",
                "Sq. reale": f.squadra_reale or "",
                "Ruolo": f.role or "",
                "Rating": f.points if f.covered else "",
            }
            for f in res.formation
        ],
        hide_index=True,
        use_container_width=True,
    )

    st.subheader("Scarsita' per ruolo (giocatori ancora liberi)")
    st.dataframe(
        [
            {
                "Ruolo": s.role,
                "Migliore libero": s.top_name or "-",
                "Rating": s.top_rating if s.top_name else "",
                "Liberi": s.liberi,
                ">=8": s.n8,
                ">=7": s.n7,
            }
            for s in res.scarcity
        ],
        hide_index=True,
        use_container_width=True,
    )


def page_campetto(ref: fe.ReferenceData, store: SQLitePurchaseStore, my_team: str):
    st.header(f"Campetto - {my_team}")
    state = fe.build_state(ref, purchases_as_dicts(store), my_team)
    if not state.rosa:
        st.info("Nessun giocatore in rosa: registra gli acquisti.")
        return

    default = fe.compute_dashboard(ref, purchases_as_dicts(store), my_team).best_module
    idx = ref.module_order.index(default) if default in ref.module_order else 0
    module_name = st.selectbox("Modulo da schierare", ref.module_order, index=idx)

    pitch, total, fuori = fe.build_pitch(ref, state.rosa, module_name)
    coperti = sum(1 for s in pitch if s.starter_name)
    st.caption(f"Totale rating {total:.2f} | slot coperti {coperti}/11 | rosa {len(state.rosa)} giocatori")

    st.pyplot(draw_pitch(pitch, module_name))

    st.subheader(f"In rosa ma non impiegabili in questo modulo ({len(fuori)})")
    st.write(", ".join(fuori) if fuori else "nessuno")


def page_listone(ref: fe.ReferenceData):
    st.header("Listone")
    query = st.text_input("Cerca giocatore")
    rows = []
    for pl in ref.players:
        if query and query.lower() not in pl.nome.lower():
            continue
        ruoli = {fe.RUOLI[i]: pl.ratings[i] for i in range(fe.NUM_RUOLI) if pl.ratings[i] >= 0}
        rows.append(
            {
                "Nome": pl.nome,
                "Sq.": pl.squadra_reale,
                "Fuori lista": "si" if pl.fuori_lista else "",
                "Ruoli": ", ".join(f"{k} {v:.1f}" for k, v in ruoli.items()),
            }
        )
    st.caption(f"{len(rows)} giocatori")
    st.dataframe(rows, hide_index=True, use_container_width=True)


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def main():
    if not lega_gate():
        st.stop()

    ref = get_reference()
    store = get_store()

    st.sidebar.title("Assistente Asta Mantra")
    my_team = st.sidebar.selectbox(
        "La mia squadra",
        ref.teams,
        index=ref.teams.index(ref.my_team) if ref.my_team in ref.teams else 0,
    )
    page = st.sidebar.radio(
        "Pagina", ["Dashboard", "Registra acquisto", "Campetto", "Listone"]
    )

    if page == "Dashboard":
        page_dashboard(ref, store, my_team)
    elif page == "Registra acquisto":
        page_registra(ref, store, my_team)
    elif page == "Campetto":
        page_campetto(ref, store, my_team)
    else:
        page_listone(ref)


if __name__ == "__main__":
    main()
