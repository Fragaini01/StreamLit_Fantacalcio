"""Assistente Asta - Fantacalcio Mantra (frontend Plotly Dash).

Porting della UI Streamlit (app.py) e del prototipo prova_streamlit.py verso Dash,
pronto per il deploy su Render con gunicorn.

Il motore di calcolo resta in fanta_engine.py e la persistenza in data_store.py:
questo modulo contiene solo il layer di presentazione (layout + callback).

Avvio locale:
    python dash_app.py
Produzione (Render):
    gunicorn dash_app:server --workers 1 --threads 4 --timeout 120
"""

from __future__ import annotations

import base64
import io
import random

import matplotlib

matplotlib.use("Agg")  # backend non interattivo: obbligatorio lato server
import matplotlib.pyplot as plt
import pandas as pd
from dash import (
    Dash,
    Input,
    Output,
    State,
    callback,
    dash_table,
    dcc,
    html,
    no_update,
)

import fanta_engine as fe
from data_store import SQLitePurchaseStore, ValidationError, validate_and_add

LEGA_NAME = "Mantra Dei Forti"
WORKBOOK = "Asta_Mantra.xlsm"
FANTA_WORKBOOK = "Fanta.xlsx"

# ----------------------------------------------------------------------------
# Risorse condivise (caricate una sola volta all'avvio del processo).
# Equivalente Dash di @st.cache_resource.
# ----------------------------------------------------------------------------
REF: fe.ReferenceData = fe.load_reference(WORKBOOK)
STORE = SQLitePurchaseStore("acquisti.db")


def purchases_as_dicts() -> list[dict]:
    return [
        {"nome": p.nome, "squadra": p.squadra, "costo": p.costo}
        for p in STORE.list_purchases()
    ]


# ----------------------------------------------------------------------------
# Dati Fanta.xlsx per la pagina "Fanta Campetti" (porting di prova_streamlit.py).
# Caricamento protetto: se il file manca la pagina mostra un avviso.
# ----------------------------------------------------------------------------
def _load_fanta(path: str) -> pd.DataFrame:
    data = pd.read_excel(path, sheet_name="Tutti", header=1)
    data["RM_1"] = data["RM"].str.split(";").str[0]
    data["RM_2"] = data["RM"].str.split(";").str[1]
    data["RM_3"] = data["RM"].str.split(";").str[2]
    return data


try:
    FANTA_DATA: pd.DataFrame | None = _load_fanta(FANTA_WORKBOOK)
    FANTA_ERROR: str | None = None
except Exception as exc:  # noqa: BLE001 - vogliamo degradare con grazia
    FANTA_DATA = None
    FANTA_ERROR = str(exc)


# ----------------------------------------------------------------------------
# Helper grafici / tabelle
# ----------------------------------------------------------------------------
def fig_to_img(fig, **img_style) -> html.Img:
    """Converte una figura matplotlib in un <img> base64 (equivalente di st.pyplot)."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=110)
    plt.close(fig)
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode("ascii")
    style = {"maxWidth": "100%", "height": "auto"}
    style.update(img_style)
    return html.Img(src=f"data:image/png;base64,{encoded}", style=style)


def data_table(table_id: str, columns: list[str], rows: list[dict], **kwargs):
    return dash_table.DataTable(
        id=table_id,
        columns=[{"name": c, "id": c} for c in columns],
        data=rows,
        style_as_list_view=True,
        style_header={"fontWeight": "bold", "backgroundColor": "#f0f2f6"},
        style_cell={
            "textAlign": "left",
            "padding": "6px 10px",
            "fontFamily": "system-ui, sans-serif",
            "fontSize": "14px",
        },
        style_table={"overflowX": "auto"},
        **kwargs,
    )


def alert(text: str, kind: str = "info"):
    colors = {
        "info": ("#eef4ff", "#1c4ed8"),
        "success": ("#e9f7ef", "#1e7e34"),
        "error": ("#fdecea", "#b71c1c"),
        "warning": ("#fff8e1", "#8a6d00"),
    }
    bg, fg = colors.get(kind, colors["info"])
    return html.Div(
        text,
        style={
            "backgroundColor": bg,
            "color": fg,
            "padding": "10px 14px",
            "borderRadius": "6px",
            "margin": "8px 0",
        },
    )


def metric_card(label: str, value) -> html.Div:
    return html.Div(
        [
            html.Div(label, style={"fontSize": "13px", "color": "#6b7280"}),
            html.Div(str(value), style={"fontSize": "24px", "fontWeight": "700"}),
        ],
        style={
            "flex": "1",
            "minWidth": "140px",
            "border": "1px solid #e5e7eb",
            "borderRadius": "8px",
            "padding": "12px 16px",
        },
    )


# ----------------------------------------------------------------------------
# Campetto (matplotlib) - porting fedele di draw_pitch/_pitch_positions da app.py
# ----------------------------------------------------------------------------
def _pitch_positions(module_name: str) -> list[tuple[float, float]]:
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
    ax.plot([0.3, 9.7, 9.7, 0.3, 0.3], [0.2, 0.2, 10.8, 10.8, 0.2], color="white", lw=2)
    ax.plot([0.3, 9.7], [5.5, 5.5], color="white", lw=1)

    positions = _pitch_positions(module_name)
    for slot, (x, y) in zip(pitch, positions):
        covered = slot.starter_name is not None
        ax.plot(
            x, y, "o", markersize=34,
            color="#d62728" if covered else "#888888",
            markeredgecolor="white", markeredgewidth=1.5, zorder=3,
        )
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
# Fanta Campetti (griglia 3x4) - porting del rendering di prova_streamlit.py
# ----------------------------------------------------------------------------
MODULI_MANTRA = {
    "3-4-3": ["Por", "Dc", "Dc", ["Dc", "B"], "E", ["M", "C"], "C", "E", ["A", "W"], ["A", "W"], "Pc"],
    "3-4-1-2": ["Por", "Dc", "Dc", ["Dc", "B"], "E", ["M", "C"], "C", "E", "T", ["Pc", "A"], ["Pc", "A"]],
    "3-4-2-1": ["Por", "Dc", "Dc", ["Dc", "B"], "E", "M", ["M", "C"], ["E", "W"], "T", ["T", "A"], "Pc"],
    "3-5-2": ["Por", "Dc", "Dc", ["Dc", "B"], "E", "M", "C", ["M", "C"], ["E", "W"], ["Pc", "A"], ["Pc", "A"]],
    "3-5-1-1": ["Por", "Dc", "Dc", ["Dc", "B"], ["E", "W"], "M", "C", "M", ["E", "W"], ["T", "A"], ["Pc", "A"]],
    "4-3-3": ["Por", "Dd", "Dc", "Dc", "Ds", "M", "C", ["M", "C"], ["W", "A"], ["Pc", "A"], ["W", "A"]],
    "4-3-1-2": ["Por", "Dd", "Dc", "Dc", "Ds", "M", "C", ["M", "C"], "T", "Pc", ["Pc", "T", "A"]],
    "4-4-2": ["Por", "Dd", "Dc", "Dc", "Ds", "E", "M", ["M", "C"], ["E", "W"], ["Pc", "A"], ["Pc", "A"]],
    "4-1-4-1": ["Por", "Dd", "Dc", "Dc", "Ds", "M", ["E", "W"], ["T", "C"], "T", "W", ["Pc", "A"]],
    "4-4-1-1": ["Por", "Dd", "Dc", "Dc", "Ds", ["E", "W"], "M", "C", ["E", "W"], ["T", "A"], ["Pc", "A"]],
    "4-2-3-1": ["Por", "Dd", "Dc", "Dc", "Ds", "M", ["M", "C"], ["W", "T"], ["W", "A"], "T", ["Pc", "A"]],
}

MODULI_POSITIONS = {
    "3-4-3": [(5, 1), (2, 3), (5, 3), (8, 3), (3, 5), (5, 5), (7, 5), (2, 7), (5, 7), (3, 9), (7, 9)],
    "3-4-1-2": [(5, 1), (2, 3), (5, 3), (8, 3), (2, 5), (4, 5), (6, 5), (8, 5), (5, 7), (3, 9), (7, 9)],
    "3-4-2-1": [(5, 1), (2, 3), (5, 3), (8, 3), (3, 5), (5, 5), (7, 5), (2, 7), (5, 7), (3, 9), (7, 9)],
    "3-5-2": [(5, 1), (2, 3), (5, 3), (8, 3), (2, 5), (4, 5), (6, 5), (8, 5), (3, 7), (5, 9), (7, 9)],
    "3-5-1-1": [(5, 1), (2, 3), (5, 3), (8, 3), (2, 5), (4, 5), (6, 5), (8, 5), (3, 7), (5, 9), (7, 9)],
    "4-3-3": [(5, 1), (2, 3), (4, 3), (6, 3), (8, 3), (2, 5), (5, 5), (8, 5), (3, 7), (5, 9), (7, 7)],
    "4-3-1-2": [(5, 1), (2, 3), (4, 3), (6, 3), (8, 3), (3, 5), (5, 5), (7, 5), (5, 7), (3, 9), (7, 9)],
    "4-4-2": [(5, 1), (2, 3), (4, 3), (6, 3), (8, 3), (2, 5), (4, 5), (6, 5), (8, 5), (3, 9), (7, 9)],
    "4-1-4-1": [(5, 1), (2, 3), (4, 3), (6, 3), (8, 3), (5, 5), (2, 7), (4, 7), (6, 7), (8, 7), (5, 9)],
    "4-4-1-1": [(5, 1), (2, 3), (4, 3), (6, 3), (8, 3), (2, 5), (4, 5), (6, 5), (8, 5), (5, 7), (5, 9)],
    "4-2-3-1": [(5, 1), (2, 3), (4, 3), (6, 3), (8, 3), (5, 5), (3, 7), (5, 7), (7, 7), (5, 9), (5, 11)],
}


def draw_campetti(nomi: list[str]):
    data = FANTA_DATA
    squadra = data[data["Nome"].isin(nomi)].copy()

    fig, axs = plt.subplots(nrows=3, ncols=4, figsize=(24, 30))
    axs = axs.flatten()
    for ax in axs:
        ax.set_facecolor("#228B22")
        ax.set_xticks([])
        ax.set_yticks([])

    for idx, modulo in enumerate(list(MODULI_MANTRA.keys())[:11]):
        schema = MODULI_MANTRA[modulo]
        ax = axs[idx]
        players: list[list] = []
        if not squadra.empty:
            squadra.loc[:, "In"] = 0
            for ruolo in schema:
                selezionati = squadra[squadra.In == 0]
                if isinstance(ruolo, list):
                    selezionati = selezionati[
                        selezionati.apply(
                            lambda row: any(
                                s == row["RM_1"] or s == row["RM_2"] or s == row["RM_3"]
                                for s in ruolo
                            ),
                            axis=1,
                        )
                    ]
                else:
                    selezionati = selezionati[
                        (selezionati.RM_1 == ruolo)
                        | (selezionati.RM_2 == ruolo)
                        | (selezionati.RM_3 == ruolo)
                    ]
                if selezionati.empty:
                    continue
                giocatore = selezionati.sort_values(by="Qt.A M", ascending=False).head(1)
                squadra.loc[giocatore.index, "In"] = 1
                players.append([giocatore.Nome.values[0], giocatore.RM.values[0]])

        used_indices: set[int] = set()
        positions = MODULI_POSITIONS.get(modulo, [(i, 1 + i) for i in range(len(schema))])
        for i, ruolo_schema in enumerate(schema):
            best_idx = None
            best_score = -1
            for j, (name, role) in enumerate(players):
                if j in used_indices:
                    continue
                if isinstance(ruolo_schema, list):
                    score = sum(r in role for r in ruolo_schema)
                else:
                    score = ruolo_schema in role
                if score > best_score:
                    best_score = score
                    best_idx = j
            if best_idx is not None and best_score:
                used_indices.add(best_idx)
                name, role = players[best_idx]
                marker_color = "red"
                display_text = name
                role_text = role
            else:
                marker_color = "gray"
                if isinstance(ruolo_schema, list):
                    role_text = "/".join(ruolo_schema)
                else:
                    role_text = ruolo_schema
                display_text = ""
            pos = positions[i]
            ax.plot(pos[0], pos[1], "o", markersize=30, color=marker_color)
            ax.text(pos[0], pos[1] + 0.2, display_text, ha="center", va="bottom",
                    fontsize=16, fontweight="bold")
            ax.text(pos[0], pos[1] - 0.5, role_text, ha="center", va="top",
                    fontsize=13, color="black")
        totale = sum(squadra[squadra.In == 1]["Qt.A M"]) if not squadra.empty else 0
        apply = 2.2 if modulo == "4-2-3-1" else 0
        ax.text(5, 10 + apply, f"Modulo: {modulo} (Totale: {totale})",
                ha="center", va="top", fontsize=18, fontweight="bold")

    fig.tight_layout()
    return fig


# ----------------------------------------------------------------------------
# App / layout
# ----------------------------------------------------------------------------
app = Dash(__name__, suppress_callback_exceptions=True, title="Assistente Asta - Mantra")
server = app.server  # entrypoint per gunicorn

NAV_LINKS = [
    ("Dashboard", "/"),
    ("Registra acquisto", "/registra"),
    ("Campetto", "/campetto"),
    ("Listone", "/listone"),
    ("Fanta Campetti", "/campetti"),
]


def gate_layout():
    return html.Div(
        [
            html.H1("Benvenuto!"),
            html.P("Inserisci il nome della lega per continuare:"),
            dcc.Input(id="gate-input", type="text", debounce=True,
                      style={"width": "320px", "padding": "8px"}),
            html.Button("Avanti", id="gate-btn", n_clicks=0,
                        style={"marginLeft": "8px", "padding": "8px 16px"}),
            html.Div(id="gate-msg"),
        ],
        style={"maxWidth": "480px", "margin": "80px auto", "fontFamily": "system-ui, sans-serif"},
    )


def app_shell():
    default_team = REF.my_team if REF.my_team in REF.teams else REF.teams[0]
    sidebar = html.Div(
        [
            html.H2("Assistente Asta Mantra", style={"fontSize": "18px"}),
            html.Label("La mia squadra", style={"fontSize": "13px", "color": "#6b7280"}),
            dcc.Dropdown(
                id="team",
                options=[{"label": t, "value": t} for t in REF.teams],
                value=default_team,
                clearable=False,
                style={"marginBottom": "16px"},
            ),
            html.Nav(
                [dcc.Link(label, href=href, style={"display": "block", "padding": "6px 0"})
                 for label, href in NAV_LINKS]
            ),
        ],
        style={
            "width": "240px",
            "minWidth": "240px",
            "padding": "20px",
            "borderRight": "1px solid #e5e7eb",
            "height": "100vh",
            "boxSizing": "border-box",
        },
    )
    content = html.Div(
        id="page-content",
        style={"flex": "1", "padding": "24px", "overflowY": "auto", "height": "100vh"},
    )
    return html.Div(
        [sidebar, content],
        style={"display": "flex", "fontFamily": "system-ui, sans-serif"},
    )


app.layout = html.Div(
    [
        dcc.Location(id="url"),
        dcc.Store(id="lega-ok", storage_type="session"),
        html.Div(id="root"),
    ]
)


# ----------------------------------------------------------------------------
# Gate lega
# ----------------------------------------------------------------------------
@callback(
    Output("root", "children"),
    Input("lega-ok", "data"),
)
def render_root(lega_ok):
    return app_shell() if lega_ok else gate_layout()


@callback(
    Output("lega-ok", "data"),
    Output("gate-msg", "children"),
    Input("gate-btn", "n_clicks"),
    State("gate-input", "value"),
    prevent_initial_call=True,
)
def check_gate(_n, value):
    if (value or "").strip() == LEGA_NAME:
        return True, no_update
    return no_update, alert("Nome lega non corretto. Riprova.", "error")


# ----------------------------------------------------------------------------
# Routing pagine
# ----------------------------------------------------------------------------
@callback(
    Output("page-content", "children"),
    Input("url", "pathname"),
    Input("team", "value"),
)
def route(pathname, team):
    if pathname == "/registra":
        return page_registra(team)
    if pathname == "/campetto":
        return page_campetto(team)
    if pathname == "/listone":
        return page_listone()
    if pathname == "/campetti":
        return page_campetti()
    return page_dashboard(team)


# ----------------------------------------------------------------------------
# Pagina: Registra acquisto
# ----------------------------------------------------------------------------
def _purchase_rows() -> list[dict]:
    return [
        {"id": p.id, "Nome": p.nome, "Squadra": p.squadra, "Costo": int(p.costo)}
        for p in STORE.list_purchases()
    ]


def page_registra(team: str):
    return html.Div(
        [
            html.H1("Registra un acquisto"),
            html.Div(
                [
                    dcc.Input(id="reg-nome", type="text", placeholder="Giocatore",
                              style={"flex": "3", "padding": "8px"}),
                    dcc.Dropdown(
                        id="reg-squadra",
                        options=[{"label": t, "value": t} for t in REF.teams],
                        value=team,
                        clearable=False,
                        style={"flex": "2", "minWidth": "160px"},
                    ),
                    dcc.Input(id="reg-costo", type="number", min=0, max=fe.CREDITI,
                              step=1, value=1, style={"flex": "1", "padding": "8px"}),
                    html.Button("Registra", id="reg-btn", n_clicks=0,
                                style={"padding": "8px 16px"}),
                ],
                style={"display": "flex", "gap": "8px", "alignItems": "center",
                       "flexWrap": "wrap", "maxWidth": "720px"},
            ),
            html.Div(id="reg-msg"),
            html.H3("Acquisti registrati in lega"),
            data_table(
                "purchases-table",
                ["Nome", "Squadra", "Costo"],
                _purchase_rows(),
                row_deletable=True,
                hidden_columns=["id"],
            ),
        ]
    )


@callback(
    Output("purchases-table", "data"),
    Output("reg-msg", "children"),
    Output("reg-nome", "value"),
    Input("reg-btn", "n_clicks"),
    State("reg-nome", "value"),
    State("reg-squadra", "value"),
    State("reg-costo", "value"),
    prevent_initial_call=True,
)
def on_register(_n, nome, squadra, costo):
    try:
        p = validate_and_add(STORE, REF, nome or "", squadra or "", costo)
    except ValidationError as exc:
        simili = [
            pl.nome for pl in REF.players if nome and nome.lower() in pl.nome.lower()
        ][:8]
        msg = [alert(str(exc), "error")]
        if simili:
            msg.append(alert("Nomi simili: " + ", ".join(simili), "info"))
        return no_update, msg, no_update
    ok = alert(f"Registrato: {p.nome} -> {p.squadra} ({int(p.costo)})", "success")
    return _purchase_rows(), ok, ""


@callback(
    Output("reg-msg", "children", allow_duplicate=True),
    Input("purchases-table", "data_previous"),
    State("purchases-table", "data"),
    prevent_initial_call=True,
)
def on_delete(previous, current):
    if previous is None:
        return no_update
    prev_ids = {r["id"] for r in previous}
    curr_ids = {r["id"] for r in current} if current else set()
    removed = prev_ids - curr_ids
    for rid in removed:
        STORE.remove_purchase(int(rid))
    if removed:
        return alert("Acquisto rimosso.", "info")
    return no_update


# ----------------------------------------------------------------------------
# Pagina: Dashboard
# ----------------------------------------------------------------------------
def page_dashboard(team: str):
    res = fe.compute_dashboard(REF, purchases_as_dicts(), team)

    children: list = [
        html.H1(f"Dashboard - {team}"),
        html.Div(
            [
                metric_card("Crediti residui", f"{int(res.credits_left)}/{fe.CREDITI}"),
                metric_card("Giocatori in rosa", res.rosa_size),
                metric_card("Portieri", res.portieri),
                metric_card("Acquisti in lega", res.n_acq),
            ],
            style={"display": "flex", "gap": "12px", "flexWrap": "wrap", "margin": "12px 0"},
        ),
    ]

    if res.messages:
        children.append(
            html.Div(
                [html.Div("- " + m) for m in res.messages],
                style={"border": "1px solid #e5e7eb", "borderRadius": "8px",
                       "padding": "12px 16px", "margin": "12px 0"},
            )
        )

    if not res.module_ranking:
        return html.Div(children)

    children.append(html.H3("Classifica moduli"))
    children.append(
        data_table(
            "tbl-moduli",
            ["Modulo", "Totale", "Media", "Coperti", "Scoperti"],
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
        )
    )

    children.append(
        html.H3(f"Formazione tipo - {res.best_module}  (totale {res.formation_total:.2f})")
    )
    children.append(
        data_table(
            "tbl-formazione",
            ["Slot", "Giocatore", "Sq. reale", "Ruolo", "Rating"],
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
        )
    )

    children.append(html.H3("Scarsita' per ruolo (giocatori ancora liberi)"))
    children.append(
        data_table(
            "tbl-scarsita",
            ["Ruolo", "Migliore libero", "Rating", "Liberi", ">=8", ">=7"],
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
        )
    )
    return html.Div(children)


# ----------------------------------------------------------------------------
# Pagina: Campetto
# ----------------------------------------------------------------------------
def page_campetto(team: str):
    state = fe.build_state(REF, purchases_as_dicts(), team)
    if not state.rosa:
        return html.Div(
            [
                html.H1(f"Campetto - {team}"),
                alert("Nessun giocatore in rosa: registra gli acquisti.", "info"),
            ]
        )

    default = fe.compute_dashboard(REF, purchases_as_dicts(), team).best_module
    default = default if default in REF.module_order else REF.module_order[0]
    return html.Div(
        [
            html.H1(f"Campetto - {team}"),
            dcc.Dropdown(
                id="campetto-module",
                options=[{"label": m, "value": m} for m in REF.module_order],
                value=default,
                clearable=False,
                style={"maxWidth": "260px", "marginBottom": "12px"},
            ),
            dcc.Store(id="campetto-team", data=team),
            html.Div(id="campetto-content"),
        ]
    )


@callback(
    Output("campetto-content", "children"),
    Input("campetto-module", "value"),
    State("campetto-team", "data"),
)
def render_campetto(module_name, team):
    state = fe.build_state(REF, purchases_as_dicts(), team)
    if not state.rosa or not module_name:
        return no_update
    pitch, total, fuori = fe.build_pitch(REF, state.rosa, module_name)
    coperti = sum(1 for s in pitch if s.starter_name)
    return html.Div(
        [
            html.Div(
                f"Totale rating {total:.2f} | slot coperti {coperti}/11 | "
                f"rosa {len(state.rosa)} giocatori",
                style={"color": "#6b7280", "marginBottom": "8px"},
            ),
            fig_to_img(draw_pitch(pitch, module_name), maxWidth="560px"),
            html.H3(f"In rosa ma non impiegabili in questo modulo ({len(fuori)})"),
            html.Div(", ".join(fuori) if fuori else "nessuno"),
        ]
    )


# ----------------------------------------------------------------------------
# Pagina: Listone
# ----------------------------------------------------------------------------
def page_listone():
    return html.Div(
        [
            html.H1("Listone"),
            dcc.Input(id="listone-query", type="text", placeholder="Cerca giocatore",
                      debounce=True, style={"width": "320px", "padding": "8px"}),
            html.Div(id="listone-content"),
        ]
    )


def _listone_rows(query: str) -> list[dict]:
    rows = []
    for pl in REF.players:
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
    return rows


@callback(
    Output("listone-content", "children"),
    Input("listone-query", "value"),
)
def render_listone(query):
    rows = _listone_rows(query or "")
    return html.Div(
        [
            html.Div(f"{len(rows)} giocatori",
                     style={"color": "#6b7280", "margin": "8px 0"}),
            data_table("tbl-listone", ["Nome", "Sq.", "Fuori lista", "Ruoli"], rows,
                       page_size=25),
        ]
    )


# ----------------------------------------------------------------------------
# Pagina: Fanta Campetti (porting di prova_streamlit.py)
# ----------------------------------------------------------------------------
def page_campetti():
    if FANTA_DATA is None:
        return html.Div(
            [
                html.H1("Fanta Campetti - Visualizzatore Moduli"),
                alert(f"Impossibile caricare {FANTA_WORKBOOK}: {FANTA_ERROR}", "error"),
            ]
        )
    return html.Div(
        [
            html.H1("Fanta Campetti - Visualizzatore Moduli"),
            dcc.Store(id="campetti-nomi", storage_type="session", data=[]),
            html.Div(
                [
                    html.Button("Genera formazione casuale", id="campetti-gen",
                                n_clicks=0, style={"padding": "8px 16px"}),
                ],
                style={"marginBottom": "12px"},
            ),
            html.Div(
                [
                    dcc.Input(id="campetti-nome", type="text",
                              placeholder="Aggiungi giocatore alla lista",
                              style={"width": "320px", "padding": "8px"}),
                    html.Button("Aggiungi", id="campetti-add", n_clicks=0,
                                style={"marginLeft": "8px", "padding": "8px 16px"}),
                ],
                style={"marginBottom": "8px"},
            ),
            html.Div(id="campetti-msg"),
            html.Div(id="campetti-content"),
        ]
    )


@callback(
    Output("campetti-nomi", "data"),
    Output("campetti-msg", "children"),
    Output("campetti-nome", "value"),
    Input("campetti-gen", "n_clicks"),
    Input("campetti-add", "n_clicks"),
    State("campetti-nome", "value"),
    State("campetti-nomi", "data"),
    prevent_initial_call=True,
)
def update_campetti_nomi(_gen, _add, nuovo, nomi):
    from dash import ctx

    nomi = list(nomi or [])
    trigger = ctx.triggered_id
    data = FANTA_DATA

    if trigger == "campetti-gen":
        portieri = (
            data[data["RM_1"] == "Por"]["Nome"]
            .sample(n=3, random_state=random.randint(0, 10000))
            .tolist()
        )
        non_portieri = (
            data[data["RM_1"] != "Por"]["Nome"]
            .sample(n=22, random_state=random.randint(0, 10000))
            .tolist()
        )
        return portieri + non_portieri, no_update, no_update

    # trigger == campetti-add
    nuovo = (nuovo or "").strip()
    if not nuovo:
        return no_update, no_update, no_update
    if nuovo in nomi:
        return no_update, alert(f"{nuovo} e' gia' stato inserito!", "warning"), no_update
    if nuovo in data["Nome"].values:
        nomi.append(nuovo)
        return nomi, alert(f"{nuovo} aggiunto!", "success"), ""
    simili = data[data["Nome"].str.contains(nuovo, case=False, na=False)]["Nome"].tolist()
    return no_update, alert("Nome non valido. Nomi simili: " + ", ".join(simili), "error"), no_update


@callback(
    Output("campetti-content", "children"),
    Input("campetti-nomi", "data"),
)
def render_campetti(nomi):
    nomi = list(nomi or [])
    data = FANTA_DATA
    squadra = data[data["Nome"].isin(nomi)]

    lista = html.Div("Nessun giocatore inserito")
    if nomi:
        items = []
        for nome in nomi:
            giocatore = squadra[squadra["Nome"] == nome]
            ruolo = giocatore.iloc[0]["RM"] if not giocatore.empty else ""
            items.append(html.Li([html.B(nome), f" ({ruolo})"]))
        lista = html.Ul(items)

    return html.Div(
        [
            html.Div([html.B("Giocatori attuali: "), ", ".join(nomi) if nomi else "-"],
                     style={"margin": "8px 0"}),
            fig_to_img(draw_campetti(nomi)),
            html.H3("Lista giocatori inseriti"),
            lista,
        ]
    )


if __name__ == "__main__":
    app.run(debug=True)
