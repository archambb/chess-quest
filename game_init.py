# game_init.py
"""
New Game initialization for Chess Quest.

This module is responsible for:
- Translating difficulty → soldier upkeep (gold_per_unit).
- Initializing player gold and army FEN.
- Initializing world economy state (bank, tax office, etc.).

It is intentionally *decoupled* from `config`:
- Callers must pass in the difficulty index explicitly.
- No imports from config in this file.
"""

from __future__ import annotations


# Difficulty names are here just for documentation / logs if you want them.
DIFFICULTY_RANKS = [
    "VERY EASY", "EASY", "NORMAL", "CHALLENGING",
    "ADVANCED", "EXPERT", "MASTER", "GRANDMASTER",
]

# Index-aligned with DIFFICULTY_RANKS (0..7)
# Matches the descriptions you wrote:
#   0: soldiers cost 0
#   1-4: cost 1
#   5-6: cost 2
#   7:   cost 3
ARMY_UPKEEP_BY_INDEX = [
    0,  # VERY EASY
    1,  # EASY
    1,  # NORMAL
    1,  # CHALLENGING
    1,  # ADVANCED
    2,  # EXPERT
    2,  # MASTER
    3,  # GRANDMASTER
]


def _clamp_index(idx: int) -> int:
    if idx < 0:
        return 0
    if idx >= len(ARMY_UPKEEP_BY_INDEX):
        return len(ARMY_UPKEEP_BY_INDEX) - 1
    return idx


def compute_gold_per_unit(difficulty_index: int) -> int:
    """
    Public helper: given a difficulty index 0..7, return upkeep cost per unit.
    """
    idx = _clamp_index(int(difficulty_index))
    return ARMY_UPKEEP_BY_INDEX[idx]


def apply_new_game_settings(g, world, difficulty_index: int | None = None) -> None:
    """
    Core entry point.

    Parameters
    ----------
    game : your main ChessScreen / Game object
        Must at least support:
          - player_gold (int)
          - player_army_fen (str)  [will be set if missing]
          - gold_per_unit (int)    [upkeep cost per non-king unit]
    world : GameWorld instance
        Must at least support:
          - army_cost_per_unit
          - bank_balance
          - bank_interest_rate
          - tax_office_balance
          - tax_office_income_per_month
          - tax_office_bonus
    difficulty_index : int | None
        0..7, aligned with DIFFICULTY_RANKS.
        If None, we try to infer from `g.difficulty_index`
        or fall back to 0.
    """
    # --- Resolve difficulty index ---
    if difficulty_index is None:
        difficulty_index = getattr(g, "difficulty_index", 0)
    difficulty_index = _clamp_index(int(difficulty_index))

    # Optional: store on game for later reference
    g.difficulty_index = difficulty_index
    difficulty_name = DIFFICULTY_RANKS[difficulty_index]
    print(f"[Init] New Game difficulty → index={difficulty_index} ({difficulty_name})")

    # --- Economy: gold & upkeep ---
    gold_per_unit = compute_gold_per_unit(difficulty_index)

    # Player starts with 0 gold; they earn gold from story / gameplay.
    g.player_gold = 0

    # Upkeep cost per non-king unit
    g.gold_per_unit = gold_per_unit

    # Keep world.army_cost_per_unit in sync so army_upkeep.py can use it.
    if hasattr(world, "army_cost_per_unit"):
        world.army_cost_per_unit = gold_per_unit
    else:
        # If not defined for some reason, attach it.
        setattr(world, "army_cost_per_unit", gold_per_unit)

    print(f"[Init] gold_per_unit set to {gold_per_unit} for this campaign.")

    # --- Army: starting FEN ---
    # Only set this if it isn't already defined by some save/load system.
    if not getattr(g, "player_army_fen", None):
        # Canonical full army for player; piece-placements only.
        g.player_army_fen = (
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"
        )
        print("[Init] player_army_fen initialized to standard starting army.")

    # --- World economy: bank & tax office ---
    # Bank
    if not hasattr(world, "bank_balance"):
        world.bank_balance = 0
    else:
        world.bank_balance = 0

    if not hasattr(world, "bank_interest_rate"):
        # Default baseline; tile 14 can override via game logic.
        world.bank_interest_rate = 0.05
    # else: keep whatever constructor set; this is your single source of truth.

    # Tax office
    world.tax_office_balance = 0
    world.tax_office_income_per_month = 0
    # A multiplier/bonus that game logic can adjust later (e.g., tile 13 bonus)
    if not hasattr(world, "tax_office_bonus"):
        world.tax_office_bonus = 0.0
    else:
        world.tax_office_bonus = 0.0

    print(
        f"[Init] World economy reset. "
        f"bank_balance={world.bank_balance}, "
        f"bank_interest_rate={world.bank_interest_rate}, "
        f"tax_office_balance={world.tax_office_balance}"
    )
