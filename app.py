"""Assistente Asta - Fantacalcio Mantra (frontend Streamlit).

Porta online la logica del file Asta_Mantra.xlsm: registro acquisti condiviso,
classifica dei moduli, formazione tipo, scarsita' per ruolo e campetto.
Il motore di calcolo e' in fanta_engine.py, la persistenza in data_store.py.
"""

from __future__ import annotations

from html import escape
from pathlib import Path

import matplotlib.pyplot as plt
import streamlit as st

import fanta_engine as fe
from data_store import SQLitePurchaseStore, ValidationError, validate_and_add

LEGA_NAME = "Mantra Dei Forti"
WORKBOOK = "Asta_Mantra.xlsm"

st.set_page_config(page_title="Assistente Asta - Mantra", layout="wide")


# --------------------------------------------------------------------------
# Colori ruoli (schema Mantra) e loghi squadre Serie A
# --------------------------------------------------------------------------
ROLE_COLORS = {
    "Por": "#E8A33D",   # portiere
    "Dd": "#3E9E5B",    # difensori
    "Ds": "#3E9E5B",
    "Dc": "#2E7D46",
    "B": "#66B981",
    "E": "#00A0B0",     # centrocampo / esterni
    "M": "#2C7FB8",
    "C": "#1F5FA6",
    "W": "#8E44AD",     # ali
    "T": "#8E44AD",     # trequartista
    "A": "#B71C1C",     # attaccanti
    "Pc": "#B71C1C",
}
DEFAULT_ROLE_COLOR = "#666666"

LOGO_DIR = Path(__file__).parent / "static" / "logos"
AVAILABLE_LOGOS = {p.stem for p in LOGO_DIR.glob("*.png")} if LOGO_DIR.exists() else set()


def role_badge(role: str, rating: float | None = None) -> str:
    if not role:
        return ""
    color = ROLE_COLORS.get(role, DEFAULT_ROLE_COLOR)
    label = role if rating is None else f"{role} {rating:.1f}"
    return (
        f"<span style='background:{color};color:#fff;padding:2px 6px;"
        f"border-radius:4px;font-size:12px;font-weight:600;"
        f"display:inline-block;margin:1px'>{escape(label)}</span>"
    )


def logo_img_html(team: str, height: int = 20) -> str:
    if team and team in AVAILABLE_LOGOS:
        return (
            f"<img src='app/static/logos/{team}.png' alt='{escape(team)}' "
            f"style='height:{height}px;vertical-align:middle;margin-right:6px'>"
        )
    return ""


def html_table(headers: list[str], rows_html: list[str]) -> str:
    head = "".join(f"<th style='text-align:left;padding:6px 8px'>{h}</th>" for h in headers)
    body = "".join(rows_html)
    return (
        "<style>.ftbl{width:100%;border-collapse:collapse}"
        ".ftbl td{padding:4px 8px;border-bottom:1px solid #eee;vertical-align:middle}"
        ".ftbl th{border-bottom:2px solid #ccc}</style>"
        f"<table class='ftbl'><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
    )


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
def login_gate(ref: fe.ReferenceData, store: SQLitePurchaseStore) -> bool:
    """Login a due ruoli: Master (password lega) o Giocatore (nome squadra)."""
    if st.session_state.get("role"):
        return True

    st.title("Benvenuto!")
    ruolo = st.radio("Accedi come", ["Giocatore", "Master"], horizontal=True)

    if ruolo == "Master":
        pwd = st.text_input("Password della lega", type="password")
        if st.button("Entra come Master"):
            if pwd == LEGA_NAME:
                st.session_state["role"] = "master"
                st.rerun()
            else:
                st.error("Password non corretta. Riprova.")
    else:
        overrides = store.get_team_names()  # orig -> custom
        taken = set(overrides.keys())
        liberi = [t for t in ref.teams if t not in taken]
        if not liberi:
            st.error("Nessuna squadra disponibile: sono tutte assegnate.")
            return False
        team = st.selectbox(
            "Scegli la tua squadra",
            liberi,
            format_func=lambda t: overrides.get(t, t),
        )
        st.caption("Dopo l'accesso potrai rinominare la tua squadra dalla barra laterale.")
        if st.button("Entra"):
            store.set_team_name(team, overrides.get(team, team))
            st.session_state["role"] = "player"
            st.session_state["player_team"] = team
            st.session_state["player_name"] = overrides.get(team, team)
            st.rerun()
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
def registra_form(
    ref: fe.ReferenceData,
    store: SQLitePurchaseStore,
    my_team: str,
    role: str,
    form_key: str,
) -> bool:
    """Form di registrazione acquisto riutilizzabile. Ritorna True se aggiunto."""
    overrides = store.get_team_names()
    disp = lambda t: overrides.get(t, t)
    giocatori = {}
    for pl in ref.players:
        if pl.fuori_lista or pl.nome in giocatori:
            continue
        giocatori[pl.nome] = pl
    nomi = sorted(giocatori)

    def fmt(n: str) -> str:
        pl = giocatori[n]
        ruoli = "/".join(
            fe.RUOLI[i] for i in range(fe.NUM_RUOLI) if pl.ratings[i] >= 0
        )
        extra = " · ".join(x for x in (ruoli, pl.squadra_reale) if x)
        return f"{n} · {extra}" if extra else n

    with st.form(form_key, clear_on_submit=True):
        c1, c2, c3 = st.columns([3, 2, 1])
        nome = c1.selectbox(
            "Giocatore", nomi, index=None,
            placeholder="Digita per cercare...", format_func=fmt,
        )
        if role == "master":
            squadra = c2.selectbox(
                "Squadra", ref.teams, index=ref.teams.index(my_team), format_func=disp
            )
        else:
            squadra = c2.selectbox(
                "Squadra", [my_team], format_func=disp, disabled=True
            )
        costo = c3.number_input("Costo", min_value=0, max_value=fe.CREDITI, value=1, step=1)
        submitted = st.form_submit_button("Registra")
    if submitted:
        try:
            p = validate_and_add(store, ref, nome, squadra, costo, budget=fe.CREDITI)
            st.toast(f"Registrato: {p.nome} → {disp(p.squadra)} ({int(p.costo)})", icon="✅")
            return True
        except ValidationError as exc:
            st.toast(str(exc), icon="⚠️")
    return False


def page_registra(ref: fe.ReferenceData, store: SQLitePurchaseStore, my_team: str, role: str):
    st.header("Registra un acquisto")
    overrides = store.get_team_names()
    disp = lambda t: overrides.get(t, t)
    giocatori = {}
    for pl in ref.players:
        if pl.fuori_lista or pl.nome in giocatori:
            continue
        giocatori[pl.nome] = pl
    nomi_giocatori = sorted(giocatori)

    def fmt_giocatore(n: str) -> str:
        pl = giocatori[n]
        ruoli = "/".join(
            fe.RUOLI[i] for i in range(fe.NUM_RUOLI) if pl.ratings[i] >= 0
        )
        extra = " · ".join(x for x in (ruoli, pl.squadra_reale) if x)
        return f"{n} · {extra}" if extra else n

    with st.form("registra", clear_on_submit=True):
        col1, col2, col3 = st.columns([3, 2, 1])
        nome = col1.selectbox(
            "Giocatore",
            options=nomi_giocatori,
            index=None,
            placeholder="Digita per cercare...",
            format_func=fmt_giocatore,
        )
        if role == "master":
            squadra = col2.selectbox(
                "Squadra", ref.teams, index=ref.teams.index(my_team), format_func=disp
            )
        else:
            squadra = col2.selectbox(
                "Squadra", [my_team], format_func=disp, disabled=True
            )
        costo = col3.number_input("Costo", min_value=0, max_value=fe.CREDITI, value=1, step=1)
        submitted = st.form_submit_button("Registra")
    if submitted:
        try:
            p = validate_and_add(store, ref, nome, squadra, costo, budget=fe.CREDITI)
            st.success(f"Registrato: {p.nome} -> {disp(p.squadra)} ({int(p.costo)})")
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
        c2.write(disp(p.squadra))
        c3.write(int(p.costo))
        can_remove = role == "master" or p.squadra == my_team
        if can_remove and c4.button("Rimuovi", key=f"del_{p.id}"):
            store.remove_purchase(p.id)
            st.rerun()


def page_dashboard(
    ref: fe.ReferenceData,
    store: SQLitePurchaseStore,
    my_team: str,
    role: str,
    note_owner: str,
):
    nome_sq = store.get_team_names().get(my_team, my_team)
    st.header(f"Dashboard - {nome_sq}")
    with st.expander("Registra un acquisto"):
        registra_form(ref, store, my_team, role, "registra_dash")
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

    mia_rosa = [p for p in store.list_purchases() if p.squadra == my_team]
    st.subheader(f"La mia rosa ({len(mia_rosa)})")
    if not mia_rosa:
        st.info("Non hai ancora acquistato giocatori.")
    else:
        rows = []
        tot = 0
        for p in mia_rosa:
            tot += int(p.costo)
            idx = ref.by_name.get(p.nome.lower())
            pl = ref.players[idx] if idx is not None else None
            if pl is not None:
                ruoli = " ".join(
                    role_badge(fe.RUOLI[i], pl.ratings[i])
                    for i in range(fe.NUM_RUOLI)
                    if pl.ratings[i] >= 0
                )
                sq_reale = f"{logo_img_html(pl.squadra_reale)}{escape(pl.squadra_reale or '')}"
            else:
                ruoli = ""
                sq_reale = ""
            rows.append(
                f"<tr><td>{escape(p.nome)}</td>"
                f"<td style='white-space:nowrap'>{sq_reale}</td>"
                f"<td>{ruoli}</td>"
                f"<td style='text-align:right'>{int(p.costo)}</td></tr>"
            )
        st.markdown(
            html_table(["Nome", "Squadra reale", "Ruoli", "Costo"], rows),
            unsafe_allow_html=True,
        )
        st.caption(f"Spesa totale: {tot} crediti")

    st.subheader("I miei giocatori per ruolo")
    by_role = {r: [] for r in fe.RUOLI}
    for p in mia_rosa:
        idx = ref.by_name.get(p.nome.lower())
        if idx is None:
            continue
        pl = ref.players[idx]
        for i, r in enumerate(fe.RUOLI):
            if pl.ratings[i] >= 0:
                by_role[r].append((pl.nome, pl.ratings[i], pl.squadra_reale))
    rows_r = []
    for r in fe.RUOLI:
        plist = sorted(by_role[r], key=lambda x: -x[1])
        chips = ", ".join(
            f"{logo_img_html(sq, 16)}{escape(nome)} ({rt:.1f})"
            for nome, rt, sq in plist
        )
        rows_r.append(
            f"<tr><td style='white-space:nowrap'>{role_badge(r)}</td>"
            f"<td>{chips}</td></tr>"
        )
    st.markdown(html_table(["Ruolo", "Giocatori"], rows_r), unsafe_allow_html=True)

    st.subheader("Spesa media per ruolo (lega)")
    sums = {r: [0.0, 0] for r in fe.RUOLI}
    for p in store.list_purchases():
        idx = ref.by_name.get(p.nome.lower())
        if idx is None:
            continue
        pl = ref.players[idx]
        for i, r in enumerate(fe.RUOLI):
            if pl.ratings[i] >= 0:
                sums[r][0] += p.costo
                sums[r][1] += 1
    rows_avg = []
    for r in fe.RUOLI:
        tot, cnt = sums[r]
        media = tot / cnt if cnt else 0
        rows_avg.append(
            f"<tr><td style='white-space:nowrap'>{role_badge(r)}</td>"
            f"<td>{media:.1f}</td><td>{cnt}</td></tr>"
        )
    st.markdown(
        html_table(["Ruolo", "Spesa media", "Acquisti"], rows_avg),
        unsafe_allow_html=True,
    )

    st.subheader("Obiettivi")
    obiettivi = store.get_notes(note_owner)
    with st.expander("Aggiungi / modifica un obiettivo"):
        tutti_o = sorted({pl.nome for pl in ref.players})
        target = st.selectbox(
            "Giocatore", tutti_o, index=None,
            placeholder="Scegli un giocatore...", key="obj_sel",
        )
        if target:
            nota_obj = st.text_area(
                "Nota", value=obiettivi.get(target, ""), key=f"obj_nota_{target}"
            )
            oc1, oc2 = st.columns([1, 1])
            if oc1.button("Salva obiettivo"):
                store.set_note(note_owner, target, nota_obj or "obiettivo")
                st.rerun()
            if obiettivi.get(target) and oc2.button("Rimuovi obiettivo"):
                store.set_note(note_owner, target, "")
                st.rerun()
    if not obiettivi:
        st.caption(
            "Nessun obiettivo salvato. Aggiungine uno qui o annota un giocatore dal Listone."
        )
    else:
        ov = store.get_team_names()
        presi = {p.nome.lower(): p.squadra for p in store.list_purchases()}
        rows_o = []
        for nome_o, nota_o in sorted(obiettivi.items()):
            idx = ref.by_name.get(nome_o.lower())
            pl = ref.players[idx] if idx is not None else None
            if pl is not None:
                ruoli = " ".join(
                    role_badge(fe.RUOLI[i], pl.ratings[i])
                    for i in range(fe.NUM_RUOLI)
                    if pl.ratings[i] >= 0
                )
                sq_reale = f"{logo_img_html(pl.squadra_reale)}{escape(pl.squadra_reale or '')}"
            else:
                ruoli = ""
                sq_reale = ""
            preso = presi.get(nome_o.lower())
            if preso is not None:
                stato_o = (
                    "<span style='background:#c62828;color:#fff;padding:2px 6px;"
                    "border-radius:4px;font-size:12px;font-weight:600'>"
                    f"{escape(ov.get(preso, preso))}</span>"
                )
            else:
                stato_o = (
                    "<span style='background:#2e7d32;color:#fff;padding:2px 6px;"
                    "border-radius:4px;font-size:12px;font-weight:600'>libero</span>"
                )
            rows_o.append(
                f"<tr><td>{escape(nome_o)}</td>"
                f"<td style='white-space:nowrap'>{sq_reale}</td>"
                f"<td>{ruoli}</td>"
                f"<td style='white-space:nowrap'>{stato_o}</td>"
                f"<td>{escape(nota_o)}</td></tr>"
            )
        st.markdown(
            html_table(
                ["Giocatore", "Squadra reale", "Ruoli", "Stato", "Nota"], rows_o
            ),
            unsafe_allow_html=True,
        )

    if not res.module_ranking:
        return

    col1, col2 = st.columns(2)
    
    with col1:
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

    with col2:
        st.subheader(f"Formazione tipo - {res.best_module}  (totale {res.formation_total:.2f})")
        st.markdown(
            html_table(
                ["Slot", "Giocatore", "Sq. reale", "Ruolo", "Rating"],
                [
                    "<tr>"
                    f"<td>{' '.join(role_badge(r) for r in f.slot_text.split('/'))}</td>"
                    f"<td>{escape(f.player_name) if f.player_name else '(scoperto)'}</td>"
                    f"<td style='white-space:nowrap'>{logo_img_html(f.squadra_reale or '')}{escape(f.squadra_reale or '')}</td>"
                    f"<td>{role_badge(f.role) if f.role else ''}</td>"
                    f"<td>{f.points if f.covered else ''}</td>"
                    "</tr>"
                    for f in res.formation
                ],
            ),
            unsafe_allow_html=True,
        )

    st.subheader("Scarsita' per ruolo (giocatori ancora liberi)")
    st.caption("Clicca un ruolo per aprire il Listone sui liberi di quel ruolo.")
    hcols = st.columns([1.2, 3, 1, 1, 1, 1])
    for hc, htxt in zip(
        hcols, ["Ruolo", "Migliore libero", "Rating", "Liberi", ">=8", ">=7"]
    ):
        hc.markdown(f"**{htxt}**")
    for s in res.scarcity:
        ccols = st.columns([1.2, 3, 1, 1, 1, 1])
        if ccols[0].button(s.role, key=f"scar_{s.role}", use_container_width=True):
            st.session_state["goto"] = "Listone"
            st.session_state["pending_role"] = s.role
            st.rerun()
        ccols[1].write(s.top_name or "-")
        ccols[2].write(f"{s.top_rating:.1f}" if s.top_name else "")
        ccols[3].write(str(s.liberi))
        ccols[4].write(str(s.n8))
        ccols[5].write(str(s.n7))


def page_campetto(ref: fe.ReferenceData, store: SQLitePurchaseStore, my_team: str):
    nome_sq = store.get_team_names().get(my_team, my_team)
    st.header(f"Campetto - {nome_sq}")
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


def page_listone(
    ref: fe.ReferenceData, store: SQLitePurchaseStore, note_owner: str
):
    st.header("Listone")
    overrides = store.get_team_names()
    taken = {p.nome.lower(): p.squadra for p in store.list_purchases()}
    notes = store.get_notes(note_owner)

    col_q, col_r, col_s, col_t = st.columns([2, 2, 2, 2])
    query = col_q.text_input("Cerca giocatore")
    ruoli_sel = col_r.multiselect("Ruoli", fe.RUOLI, key="listone_ruoli")
    squadre = sorted({pl.squadra_reale for pl in ref.players if pl.squadra_reale})
    squadre_sel = col_s.multiselect("Squadra reale", squadre, key="listone_squadre")
    stato_sel = col_t.selectbox(
        "Stato", ["Tutti", "Liberi", "Presi"], key="listone_stato"
    )

    with st.expander("Note private (visibili solo a te)"):
        nomi_note = sorted({pl.nome for pl in ref.players})
        sel_nota = st.selectbox(
            "Giocatore", nomi_note, index=None,
            placeholder="Scegli un giocatore...", key="nota_sel",
        )
        if sel_nota:
            testo = st.text_area(
                "Nota", value=notes.get(sel_nota, ""), key=f"nota_txt_{sel_nota}"
            )
            b1, b2 = st.columns([1, 1])
            if b1.button("Salva nota"):
                store.set_note(note_owner, sel_nota, testo)
                st.rerun()
            if notes.get(sel_nota) and b2.button("Elimina nota"):
                store.set_note(note_owner, sel_nota, "")
                st.rerun()

    rows_html = []
    for pl in ref.players:
        if query and query.lower() not in pl.nome.lower():
            continue
        if squadre_sel and pl.squadra_reale not in squadre_sel:
            continue
        pl_ruoli = [fe.RUOLI[i] for i in range(fe.NUM_RUOLI) if pl.ratings[i] >= 0]
        if ruoli_sel and not any(r in ruoli_sel for r in pl_ruoli):
            continue
        preso_da = taken.get(pl.nome.lower())
        is_taken = preso_da is not None
        if stato_sel == "Liberi" and is_taken:
            continue
        if stato_sel == "Presi" and not is_taken:
            continue
        if is_taken:
            nome_sq = overrides.get(preso_da, preso_da)
            stato_cell = (
                "<span style='background:#c62828;color:#fff;padding:2px 6px;"
                "border-radius:4px;font-size:12px;font-weight:600'>"
                f"{escape(nome_sq)}</span>"
            )
        else:
            stato_cell = (
                "<span style='background:#2e7d32;color:#fff;padding:2px 6px;"
                "border-radius:4px;font-size:12px;font-weight:600'>libero</span>"
            )
        ruoli = " ".join(
            role_badge(fe.RUOLI[i], pl.ratings[i])
            for i in range(fe.NUM_RUOLI)
            if pl.ratings[i] >= 0
        )
        squadra = f"{logo_img_html(pl.squadra_reale)}{escape(pl.squadra_reale or '')}"
        nota_txt = notes.get(pl.nome, "")
        nota_cell = (
            f"<span style='color:#555;font-style:italic'>{escape(nota_txt)}</span>"
            if nota_txt else ""
        )
        rows_html.append(
            f"<tr><td>{escape(pl.nome)}</td>"
            f"<td style='white-space:nowrap'>{squadra}</td>"
            f"<td>{ruoli}</td>"
            f"<td style='white-space:nowrap'>{stato_cell}</td>"
            f"<td>{nota_cell}</td></tr>"
        )
    st.caption(f"{len(rows_html)} giocatori")
    st.markdown(
        html_table(["Nome", "Squadra reale", "Ruoli", "Stato", "Nota"], rows_html),
        unsafe_allow_html=True,
    )


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def main():
    ref = get_reference()
    store = get_store()

    if not login_gate(ref, store):
        st.stop()

    role = st.session_state["role"]

    # navigazione da pulsanti (es. Scarsita' -> Listone filtrato)
    if "goto" in st.session_state:
        st.session_state["nav_page"] = st.session_state.pop("goto")
    if "pending_role" in st.session_state:
        st.session_state["listone_ruoli"] = [st.session_state.pop("pending_role")]
        st.session_state["listone_squadre"] = []
        st.session_state["listone_stato"] = "Liberi"

    overrides = store.get_team_names()
    disp = lambda t: overrides.get(t, t)

    st.sidebar.title("Assistente Asta Mantra")

    if role == "master":
        st.sidebar.caption("Ruolo: Master")
        my_team = st.sidebar.selectbox(
            "La mia squadra",
            ref.teams,
            index=ref.teams.index(ref.my_team) if ref.my_team in ref.teams else 0,
            format_func=disp,
        )
    else:
        my_team = st.session_state["player_team"]
        st.sidebar.caption(f"Ruolo: Giocatore - {disp(my_team)}")
        with st.sidebar.expander("Rinomina la tua squadra"):
            nuovo = st.text_input("Nuovo nome squadra", value=disp(my_team))
            if st.button("Salva nome"):
                nuovo_clean = (nuovo or "").strip()
                altri = {disp(t).casefold() for t in ref.teams if t != my_team}
                if not nuovo_clean:
                    st.error("Il nome non puo' essere vuoto.")
                elif nuovo_clean.casefold() in altri:
                    st.error("Nome gia' in uso da un'altra squadra.")
                else:
                    store.set_team_name(my_team, nuovo_clean)
                    st.session_state["player_name"] = nuovo_clean
                    st.success("Nome squadra aggiornato.")
                    st.rerun()

    page = st.sidebar.radio(
        "Pagina", ["Dashboard", "Registra acquisto", "Campetto", "Listone"],
        key="nav_page",
    )

    if role == "master":
        st.sidebar.divider()
        with st.sidebar.expander("Rinomina squadre"):
            target = st.selectbox(
                "Squadra", ref.teams, format_func=disp, key="rin_target"
            )
            nuovo_nome = st.text_input("Nuovo nome", value=disp(target), key="rin_nome")
            if st.button("Rinomina squadra"):
                nn = (nuovo_nome or "").strip()
                altri = {disp(t).casefold() for t in ref.teams if t != target}
                if not nn:
                    st.error("Il nome non puo' essere vuoto.")
                elif nn.casefold() in altri:
                    st.error("Nome gia' in uso da un'altra squadra.")
                else:
                    store.set_team_name(target, nn)
                    st.success("Squadra rinominata.")
                    st.rerun()
        with st.sidebar.expander("Amministrazione asta"):
            st.caption("Termina l'asta: cancella acquisti e nomi squadre.")
            conferma = st.checkbox("Confermo di voler azzerare tutto")
            if st.button(
                "Termina asta e azzera tutto", type="primary", disabled=not conferma
            ):
                store.clear()
                store.clear_team_names()
                st.success("Asta terminata: tutto azzerato.")
                st.rerun()

    st.sidebar.divider()
    if st.sidebar.button("Esci"):
        for k in ("role", "player_team", "player_name"):
            st.session_state.pop(k, None)
        st.rerun()

    note_owner = "__master__" if role == "master" else my_team
    if page == "Dashboard":
        page_dashboard(ref, store, my_team, role, note_owner)
    elif page == "Registra acquisto":
        page_registra(ref, store, my_team, role)
    elif page == "Campetto":
        page_campetto(ref, store, my_team)
    else:
        page_listone(ref, store, note_owner)


if __name__ == "__main__":
    main()
