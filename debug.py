# debug.py
def Debug_GiveAllSpells():
    return [
        "Desert Sun",
        "Flood",
        "Granite Elf",
        "Greed",
        "Heal Pawns",
        "Ice Blast",
        "Inspire Soldier",
        "Meteor Shower",
        "Mirror Armies",
        "One With Light",
        "Orb of Premonition",
        "Sacrifice",
        "Shadow Step",
        "Summon Elf",
        "Summon Undead Elves",
        "Wind Storm"
    ]


def Debug_GiveAllPowerups():
    # "Power-ups - lots of power-ups!" - Neo
    powerups = {
        "bombs": 999,
        "freezes": 999,
        "swaps": 999,
        "shields": 999,
        "advanced_shields": 999,
        "promotions": 999,
        "time_warps": 999,
        "magnets": 999
    }
    return powerups


def Debug_GiveAllGear(gear_order):
    """
    Turn on all gear for debug runs.
    `gear_order` should be g.config.GEAR_ORDER (list of keys).
    Using '1' here since gear is usually binary (owned / not-owned).
    Change to 999 if you later make them consumable.
    """
    return {name: 1 for name in gear_order}

def Debug_CompleteQuest(g, index: int):
    """
    Force-completes one of the currently active quest cards while in debug mode.

    index: 0-based index of the quest card (0,1,2 → first three).
    """
    quests = g.quests
    if not quests.active_quests:
        print("[DEBUG] No active quests to complete.")
        return

    if index < 0 or index >= len(quests.active_quests):
        print(f"[DEBUG] Quest index {index} is out of range. Active quests: {quests.active_quests}")
        return

    qid = quests.active_quests[index]
    quest_data = quests.quest_lookup.get(qid)
    reward = None

    if quest_data:
        win_pairs = quest_data.get("win_reward_pairs") or []
        if win_pairs:
            reward = win_pairs[0].get("reward")

    print(f"[DEBUG] Forcing completion of Quest #{qid} ({quest_data.get('title','Unknown')})")

    # This calls the game's normal quest animation + reward system.
    quests.win_quest(qid, reward)
