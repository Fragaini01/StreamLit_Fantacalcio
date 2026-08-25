"""Test del motore fanta_engine: ottimizzatore, copertura, stato lega."""

from __future__ import annotations

import os

import pytest

import fanta_engine as fe
from fanta_engine import Player, ROLE_INDEX, NUM_RUOLI, RUOLI


def make_player(idx: int, nome: str, roles: dict[str, float], sq: str = "SqX", fuori: bool = False) -> Player:
    ratings = [-1.0] * NUM_RUOLI
    for r, v in roles.items():
        ratings[ROLE_INDEX[r]] = v
    return Player(idx=idx, nome=nome, squadra_reale=sq, fuori_lista=fuori, ratings=ratings)


def slots_from_text(texts: list[str]) -> list[list[int]]:
    return [[ROLE_INDEX[p] for p in t.split("/")] for t in texts]


# Modulo giocattolo a 11 slot: Por + 10 ruoli semplici
TOY_MODULE = slots_from_text(
    ["Por", "Dc", "Dc", "Dc", "E", "M", "C", "E", "W", "A", "Pc"]
)


def test_solve_empty_roster():
    sol = fe.solve_slots([], TOY_MODULE, [])
    assert sol.total == 0.0
    assert sol.covered == 0


def test_solve_assigns_and_scores():
    players = [
        make_player(0, "Portiere", {"Por": 6.0}),
        make_player(1, "Dif", {"Dc": 7.0}),
        make_player(2, "Att", {"A": 9.0, "Pc": 8.0}),
    ]
    sol = fe.solve_slots([0, 1, 2], TOY_MODULE, players)
    assert sol.covered == 3
    # totale = 6 + 7 + max(A=9 su slot A, Pc=8 su slot Pc) => l'ottimo mette Att su A(9)
    assert sol.total == pytest.approx(6.0 + 7.0 + 9.0)


def test_coverage_beats_rating():
    # Un fuoriclasse che copre un solo slot vs due giocatori mediocri che coprono due slot.
    players = [
        make_player(0, "Fuoriclasse", {"Dc": 10.0}),
        make_player(1, "MedioDc", {"Dc": 5.0}),
        make_player(2, "MedioE", {"E": 5.0}),
    ]
    # Con soli slot Dc ed E disponibili, l'ottimo copre entrambi (2 slot) invece di 1 solo.
    module = slots_from_text(["Dc", "E"]) + [[ROLE_INDEX["Pc"]]] * 9
    sol = fe.solve_slots([0, 1, 2], module, players)
    assert sol.covered == 2  # copertura massimizzata
    # Slot Dc preso dal migliore fra i Dc rimasti, slot E dal MedioE
    assert sol.total == pytest.approx(10.0 + 5.0)


def test_ineligible_player_not_placed():
    players = [make_player(0, "SoloAtt", {"A": 8.0})]
    module = slots_from_text(["Por"]) + [[ROLE_INDEX["Dc"]]] * 10
    sol = fe.solve_slots([0], module, players)
    assert sol.covered == 0
    assert sol.total == 0.0


def test_multi_role_slot_picks_best():
    players = [make_player(0, "Jolly", {"M": 6.0, "C": 8.0})]
    module = slots_from_text(["M/C"]) + [[ROLE_INDEX["Pc"]]] * 10
    sol = fe.solve_slots([0], module, players)
    assert sol.covered == 1
    assert sol.roles[0] == ROLE_INDEX["C"]
    assert sol.total == pytest.approx(8.0)


def _mini_ref() -> fe.ReferenceData:
    players = [
        make_player(0, "Gigi", {"Por": 6.0}),
        make_player(1, "Bobo", {"A": 9.0}),
    ]
    by_name = {p.nome.lower(): p.idx for p in players}
    modules = {"1-0-0": slots_from_text(["Por"]) + [[ROLE_INDEX["A"]]] * 10}
    return fe.ReferenceData(
        players=players,
        by_name=by_name,
        modules=modules,
        module_order=["1-0-0"],
        teams=["Squadra 1", "Squadra 2"],
        my_team="Squadra 1",
    )


def test_build_state_splits_rosa_and_presi():
    ref = _mini_ref()
    purchases = [
        {"nome": "Gigi", "squadra": "Squadra 1", "costo": 30},
        {"nome": "Bobo", "squadra": "Squadra 2", "costo": 100},
        {"nome": "Sconosciuto", "squadra": "Squadra 1", "costo": 5},
    ]
    state = fe.build_state(ref, purchases, "Squadra 1")
    assert state.rosa == [0]              # solo Gigi è mio e nel listone
    assert state.presi == {"Gigi", "Bobo"}
    assert state.spent == pytest.approx(30.0)
    assert state.n_acq == 3


def test_scarcity_excludes_taken_and_fuori_lista():
    ref = _mini_ref()
    ref.players[1].fuori_lista = True  # Bobo fuori lista => non conta come libero
    rows = fe.scarcity(ref, presi=set())
    a_row = next(r for r in rows if r.role == "A")
    assert a_row.liberi == 0


@pytest.mark.skipif(not os.path.exists("Asta_Mantra.xlsm"), reason="workbook non presente")
def test_load_reference_smoke():
    ref = fe.load_reference("Asta_Mantra.xlsm")
    assert len(ref.players) > 100
    assert len(ref.module_order) == 11
    assert len(ref.teams) == 8
    # ogni modulo ha 11 slot
    for slots in ref.modules.values():
        assert len(slots) == fe.NSLOT
