import streamlit as st
st.set_page_config(layout="wide")
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Carica dati
@st.cache_data
def load_data():
    data = pd.read_excel("Fanta.xlsx", sheet_name="Tutti", header=1)
    data['RM_1'] = data['RM'].str.split(';').str[0]
    data['RM_2'] = data['RM'].str.split(';').str[1]
    data['RM_3'] = data['RM'].str.split(';').str[2]
    return data

data = load_data()

moduli_mantra = {
    "3-4-3": ["Por" , "Dc", "Dc", ["Dc", "B"], "E", ["M", "C"], "C", "E", ["A", "W"],  ["A", "W"], "Pc"],
    "3-4-1-2": ["Por" , "Dc", "Dc", ["Dc", "B"], "E", ["M", "C"], "C", "E", "T", ["Pc","A"], ["Pc","A"]],
    "3-4-2-1": ["Por" , "Dc", "Dc", ["Dc", "B"], "E", "M", ["M", "C"], ["E","W"], "T", ["T", "A"], "Pc"],
    "3-5-2": ["Por" , "Dc", "Dc", ["Dc", "B"], "E", "M", "C", ["M", "C"], ["E","W"], ["Pc","A"], ["Pc","A"]],
    "3-5-1-1": ["Por" , "Dc", "Dc", ["Dc", "B"], ["E","W"], "M", "C", "M", ["E","W"], ["T", "A"], ["Pc","A"]],
    "4-3-3": ["Por" , "Dd", "Dc", "Dc", "Ds", "M", "C", ["M", "C"], ["W", "A"], ["Pc","A"], ["W", "A"]],
    "4-3-1-2": ["Por" , "Dd", "Dc", "Dc", "Ds", "M", "C", ["M", "C"], "T", "Pc",["Pc","T","A"]],
    "4-4-2": ["Por" , "Dd", "Dc", "Dc", "Ds", "E", "M",["M", "C"], ["E","W"], ["Pc","A"], ["Pc","A"]],
    "4-1-4-1": ["Por" , "Dd", "Dc", "Dc", "Ds", "M", ["E","W"], ["T", "C"], "T", "W", ["Pc","A"]],
    "4-4-1-1": ["Por" , "Dd", "Dc", "Dc", "Ds", ["E","W"], "M","C", ["E","W"], ["T", "A"], ["Pc","A"]],
    "4-2-3-1": ["Por" , "Dd", "Dc", "Dc", "Ds", "M", ["M", "C"], ["W", "T"], ["W", "A"], "T", ["Pc","A"]]
}

moduli_positions = {
    "3-4-3": [ (5, 1), (2, 3), (5, 3), (8, 3), (3, 5), (5, 5), (7, 5), (2, 7), (5, 7), (3, 9), (7, 9) ],
    "3-4-1-2": [ (5, 1), (2, 3), (5, 3), (8, 3), (2, 5), (4, 5), (6, 5), (8, 5), (5, 7), (3, 9), (7, 9) ],
    "3-4-2-1": [ (5, 1), (2, 3), (5, 3), (8, 3), (3, 5), (5, 5), (7, 5), (2, 7), (5, 7), (3, 9), (7, 9) ],
    "3-5-2": [ (5, 1), (2, 3), (5, 3), (8, 3), (2, 5), (4, 5), (6, 5), (8, 5), (3, 7), (5, 9), (7, 9) ],
    "3-5-1-1": [ (5, 1), (2, 3), (5, 3), (8, 3), (2, 5), (4, 5), (6, 5), (8, 5), (3, 7), (5, 9), (7, 9) ],
    # Difesa a 4 in linea: Dd, Dc, Dc, Ds
    "4-3-3": [ (5, 1), (2, 3), (4, 3), (6, 3), (8, 3), (2, 5), (5, 5), (8, 5), (3, 7), (5, 9), (7, 7) ],
    "4-3-1-2": [ (5, 1), (2, 3), (4, 3), (6, 3), (8, 3), (3, 5), (5, 5), (7, 5), (5, 7), (3, 9), (7, 9) ],
    "4-4-2": [ (5, 1), (2, 3), (4, 3), (6, 3), (8, 3), (2, 5), (4, 5), (6, 5), (8, 5), (3, 9), (7, 9) ],
    "4-1-4-1": [ (5, 1), (2, 3), (4, 3), (6, 3), (8, 3), (5, 5), (2, 7), (4, 7), (6, 7), (8, 7), (5, 9) ],
    "4-4-1-1": [ (5, 1), (2, 3), (4, 3), (6, 3), (8, 3), (2, 5), (4, 5), (6, 5), (8, 5), (5, 7), (5, 9) ],
    "4-2-3-1": [ (5, 1), (2, 3), (4, 3), (6, 3), (8, 3), (5, 5), (3, 7), (5, 7), (7, 7), (5, 9), (5, 11) ]
}


st.title("Fanta Campetti - Visualizzatore Moduli")

# Gestione lista giocatori
if 'nomi' not in st.session_state:
    st.session_state['nomi'] = []

with st.form("aggiungi_giocatore"):
    nuovo_nome = st.text_input("Aggiungi giocatore alla lista:")
    aggiungi = st.form_submit_button("Aggiungi")
    if aggiungi and nuovo_nome:
        if nuovo_nome in st.session_state['nomi']:
            st.warning(f"{nuovo_nome} è già stato inserito!")
        elif nuovo_nome in data['Nome'].values:
            st.session_state['nomi'].append(nuovo_nome)
            st.success(f"{nuovo_nome} aggiunto!")
        else:
            simili = data[data['Nome'].str.contains(nuovo_nome, case=False, na=False)]["Nome"].tolist()
            st.error("Nome non valido. Nomi simili: " + ", ".join(simili))

st.write("**Giocatori attuali:**", st.session_state['nomi'])

squadra = data[data['Nome'].isin(st.session_state['nomi'])].copy()

# Visualizza tutti i moduli

# Subplot: 4x3, l'ultimo (axs[-1]) per la lista giocatori

# Subplot: 3x4, primi 11 per i moduli, ultimo per la lista
fig, axs = plt.subplots(nrows=3, ncols=4, figsize=(24, 30))
axs = axs.flatten()

for ax in axs:
    ax.set_facecolor('#228B22')  # verde prato
    ax.set_xticks([])
    ax.set_yticks([])

for idx, modulo in enumerate(list(moduli_mantra.keys())[:11]):
    schema = moduli_mantra[modulo]
    ax = axs[idx]
    players = []
    if not squadra.empty:
        squadra.loc[:, 'In'] = 0
        for ruolo in schema:
            selezionati = squadra[squadra.In == 0]
            if isinstance(ruolo, list):
                selezionati = selezionati[
                    selezionati.apply(lambda row: any(s == row['RM_1'] or s == row['RM_2'] or s == row['RM_3'] for s in ruolo), axis=1)
                ]
            else:
                selezionati = selezionati[
                    (selezionati.RM_1 == ruolo) |
                    (selezionati.RM_2 == ruolo) |
                    (selezionati.RM_3 == ruolo)
                ]
            if selezionati.empty:
                continue
            giocatore = selezionati.sort_values(by='Qt.A M', ascending=False).head(1)
            squadra.loc[giocatore.index, 'In'] = 1
            players.append([giocatore.Nome.values[0], giocatore.RM.values[0]])
    used_indices = set()
    positions = moduli_positions.get(modulo, [(i, 1 + i) for i in range(len(schema))])
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
            marker_color = 'red'
            display_text = name
            role_text = role
        else:
            marker_color = 'gray'
            if isinstance(ruolo_schema, list):
                role_text = "/".join(ruolo_schema)
            else:
                role_text = ruolo_schema
            display_text = ""
        pos = positions[i]
        ax.plot(pos[0], pos[1], 'o', markersize=30, color=marker_color)
        ax.text(pos[0], pos[1]+0.2, display_text, ha='center', va='bottom', fontsize=16, fontweight='bold')
        ax.text(pos[0], pos[1]-0.5, role_text, ha='center', va='top', fontsize=13, color='black')
    totale = sum(squadra[squadra.In == 1]['Qt.A M']) if not squadra.empty else 0
    ax.text(5, 10, f"Modulo: {modulo} (Totale: {totale})", ha='center', va='top', fontsize=18, fontweight='bold')


fig.tight_layout()
st.pyplot(fig)

# Lista giocatori sotto l'immagine
st.subheader("Lista giocatori inseriti")
if st.session_state['nomi']:
    for nome in st.session_state['nomi']:
        giocatore = squadra[squadra['Nome'] == nome]
        ruolo = giocatore.iloc[0]['RM'] if not giocatore.empty else ""
        st.markdown(f"- **{nome}** ({ruolo})")
else:
    st.info("Nessun giocatore inserito")
