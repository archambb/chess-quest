# Overworld Quest Help

This guide explains how to build, connect, validate, and test overworld quests in Chess Quest.

## Quick Start

Use the GUI editor:

```powershell
python tools\overworld_quest_editor.py
```

Use the story editor:

```powershell
python data\story_editor.py
```

Validate overworld quests from the command line:

```powershell
python tools\overworld_quest_editor.py validate
```

## Main Files

- `data/overworld_quests.json`
  Defines overworld quest data.

- `overworld_quest_manager.py`
  Loads quests, tracks active/failed/completed state, owns conditional dialog, tracks global story flags, handles expiration, and injects board objective cards.

- `tools/overworld_quest_editor.py`
  GUI editor for overworld quests.

- `data/story_editor.py`
  GUI editor for stories and frames.

- `data/stories.json`
  Maps story IDs to frame IDs.

- `data/frames.json`
  Defines story text, options, and story rewards.

- `quest_cards.py`
  Builds normal quest cards and overworld quest cards.

## Quest Lifecycle

Overworld quests are intended to start from stories.

A typical flow:

1. A story plays.
2. The story or future story hook starts an overworld quest.
3. The quest appears in the overworld quest journal.
4. The player travels normally.
5. The quest manager checks location, flags, gear, gold, and other conditions.
6. Conditional dialog appears when a step is available.
7. Some steps may inject quest cards into specific combat boards.
8. Completing or failing the quest plays an outcome story.
9. The outcome story grants flags, gold, or permanent equipment.

## Quest Data Structure

Basic quest shape:

```json
{
  "id": "dying_king",
  "name": "The Dying King",
  "description": "The king is fading. Dark and living remedies both remain possible.",
  "timer": {
    "months": null
  },
  "start_location": {
    "stage_id": 0
  },
  "locations": {
    "life_wizard": {
      "stage_id": 11
    }
  },
  "availability": {
    "all": [
      {
        "type": "flag_absent",
        "flag": "king_alive"
      }
    ]
  },
  "first_step": "choose_cure",
  "steps": [],
  "outcomes": {}
}
```

## Timers

Quest timers use normal overworld time.

Every normal move to a new territory advances one month. The quest system does not force extra travel time.

Infinite timer:

```json
"timer": {
  "months": null
}
```

Expires after 6 normal overworld moves:

```json
"timer": {
  "months": 6
}
```

Expired quests are moved into failed quest history.

## Availability Conditions

Availability uses condition objects.

Examples:

```json
{ "type": "flag_present", "flag": "king_is_dying" }
{ "type": "flag_absent", "flag": "king_dead" }
{ "type": "gold_at_least", "amount": 10 }
{ "type": "gear_owned", "id": "crystal_staff" }
{ "type": "quest_completed", "quest_id": "dying_king" }
{ "type": "quest_failed", "quest_id": "dying_king" }
{ "type": "current_stage", "stage_id": 11 }
{ "type": "area_state", "stage_id": 7, "state": "lost" }
{ "type": "area_state", "stage_id": 11, "state": "won" }
{ "type": "area_state", "stage_id": 3, "state": "untouched" }
```

Combine with `all`:

```json
"availability": {
  "all": [
    { "type": "flag_present", "flag": "king_is_dying" },
    { "type": "gold_at_least", "amount": 10 }
  ]
}
```

Combine with `any`:

```json
"availability": {
  "any": [
    { "type": "gear_owned", "id": "crystal_staff" },
    { "type": "flag_present", "flag": "life_wizard_trusts_you" }
  ]
}
```

## Steps

Steps define the current state of an active quest.

Dialog step:

```json
{
  "id": "convince_life_wizard",
  "name": "Convince the Wizard of Life",
  "type": "dialog",
  "choices": []
}
```

Story step:

```json
{
  "id": "arrival",
  "name": "Arrival",
  "type": "story",
  "story": "Dying_King_Arrival"
}
```

Board objective step:

```json
{
  "id": "astral_trial",
  "name": "Complete the Astral Trial",
  "type": "board",
  "board_objectives": []
}
```

## Conditional Dialog Choices

The overworld quest manager owns conditional dialog.

Choice with gold requirement and cost:

```json
{
  "id": "pay_10_gold",
  "text": "Pay 10 gold for the healing rite.",
  "requires": [
    { "type": "current_stage", "stage_id": 11 },
    { "type": "gold_at_least", "amount": 10 }
  ],
  "costs": {
    "gold": 10
  },
  "outcome": "king_healed"
}
```

Choice with equipment requirement:

```json
{
  "id": "offer_crystal_staff",
  "text": "Offer the Crystal Staff as proof of good faith.",
  "requires": [
    { "type": "current_stage", "stage_id": 11 },
    { "type": "gear_owned", "id": "crystal_staff" }
  ],
  "outcome": "king_healed"
}
```

Choice that advances to another step:

```json
{
  "id": "seek_life_wizard",
  "text": "Petition the Wizard of Life.",
  "requires": [
    { "type": "current_stage", "stage_id": 11 }
  ],
  "next_step": "convince_life_wizard"
}
```

Choice that sets flags:

```json
{
  "id": "raise_as_zombie",
  "text": "Seek the grave lands.",
  "set_flags": ["king_raised_as_zombie"],
  "outcome": "king_zombie"
}
```

## Outcomes

Outcomes usually play a story and complete or fail the quest.

Successful outcome:

```json
"king_healed": {
  "story": "Dying_King_Healed",
  "set_flags": ["king_alive"],
  "clear_flags": ["king_dead", "king_is_dying"],
  "complete": true
}
```

Failure outcome:

```json
"king_dies": {
  "story": "Dying_King_Dead",
  "set_flags": ["king_dead"],
  "clear_flags": ["king_is_dying"],
  "fail": true
}
```

Important: overworld quest rewards should be granted through the outcome story, not directly by the quest outcome.

## Story Rewards

Story rewards live in `frames.json` as `return_rewards`.

Example:

```json
"305": {
  "text": "The king rises, breathing again.",
  "return_rewards": {
    "gold": 5,
    "gear": ["gear_key"],
    "set_flags": ["king_alive"],
    "clear_flags": ["king_is_dying"]
  }
}
```

Supported story rewards:

```json
{
  "powerups": {
    "shields": 2,
    "promotions": 1
  },
  "spells": [
    "Granite Elf"
  ],
  "gold": 5,
  "gear": [
    "gear_key"
  ],
  "set_flags": [
    "king_alive"
  ],
  "clear_flags": [
    "king_is_dying"
  ]
}
```

Gear IDs come from `config.GEAR_ORDER`.

## Building Story Elements

Open:

```powershell
python data\story_editor.py
```

Recommended story workflow:

1. Create or select a story node.
2. Add frames.
3. Add text.
4. Add frame art by dragging PNGs into the frame image strip.
5. Add options if the story branches.
6. Add rewards on the frame that should grant them.
7. Save frame.
8. Use the validation panel to check missing stories, frames, flags, and gear.

The story editor now knows about overworld quest references. If an overworld quest references a missing story, use:

```text
Overworld -> Create Missing Overworld Stories
```

This creates placeholder story nodes and starter frames for missing story IDs.

## Story Asset Naming

Frame art:

```text
assets/GFX/frame/frame_<frame_id>_1.png
assets/GFX/frame/frame_<frame_id>_2.png
```

Voice:

```text
assets/SFX/voice/frame/frame_voice_<frame_id>.wav
```

Music:

```text
assets/SFX/music/frame/frame_music_<frame_id>.ogg
```

The story player also accepts variants with suffixes, following the existing random asset lookup pattern.

## Overworld Quest Card Art

Overworld quest card art goes here:

```text
assets/GFX/overworld_quests/cards/
```

Primary naming convention:

```text
assets/GFX/overworld_quests/cards/<quest_id>.png
```

Example:

```text
assets/GFX/overworld_quests/cards/dying_king.png
```

If a board objective has its own ID, the system can also fall back to:

```text
assets/GFX/overworld_quests/cards/<objective_id>.png
```

The editor has an import button that copies a PNG into the correct location as:

```text
<quest_id>.png
```

Recommended art size:

```text
420 x 620
```

The card renderer crops/fits the art into the card frame, then renders title/rules text on top.

## Board Objectives

Board objectives inject temporary quest cards into the normal combat quest card hand.

They only appear on boards whose `stage_id` matches the objective.

All active cards, including overworld cards, must be completed before equipment can be used.

Currently supported generic objective:

```json
"type": "hold_piece_on_squares"
```

Example:

```json
{
  "id": "astral_center_pawn",
  "stage_id": 10,
  "title": "Hold the Astral Center",
  "rules": "Keep a pawn in the center for 10 turns.",
  "quest_card": {
    "feedback": ["Astral Center Turns"],
    "objective": {
      "type": "hold_piece_on_squares",
      "piece_type": "pawn",
      "squares": ["d4", "e4", "d5", "e5"],
      "stat_key": "Astral Center Turns"
    },
    "win_reward_pairs": [
      {
        "to_win": {
          "Astral Center Turns": {
            "op": ">=",
            "value": 10
          }
        },
        "reward": {}
      }
    ]
  },
  "outcome": "astral_trial_complete"
}
```

If you need a new objective type, add the logic in:

```text
quest_info.py
QuestInfo.update_injected_board_objectives()
```

## Quest Journal

In the overworld, press:

```text
Q
```

This opens the overworld quest journal with:

- Active
- Failed

It shows quest name, current step, and current location.

## Validation

Run:

```powershell
python tools\overworld_quest_editor.py validate
```

This checks:

- Duplicate quest IDs
- Missing quest names
- Invalid `steps` / `outcomes` shapes
- Missing story references from overworld quests
- Missing frame IDs from stories
- Unknown gear rewards
- Basic stage ID range for board objectives

The story editor also shows validation awareness for:

- Missing overworld story references
- Missing frames
- Unknown gear rewards
- Story flags that are not known from overworld quest data

## Testing Checklist

Before testing in-game:

1. Run overworld quest validation.
2. Open the story editor and validate story links.
3. Confirm every quest outcome story exists.
4. Confirm every story has at least one frame.
5. Confirm every frame with rewards uses valid gear IDs.
6. Confirm card art exists for important quest IDs.
7. Confirm board objectives use the correct `stage_id`.

In-game test path:

1. Start or load a campaign.
2. Trigger the story that starts the quest.
3. Open the overworld journal with `Q`.
4. Move normally across the overworld.
5. Confirm quest timers advance only on normal territory movement.
6. Travel to the required stage.
7. Confirm conditional dialog appears only when requirements are met.
8. If the quest has a board objective, enter the matching stage.
9. Confirm the overworld quest card appears alongside normal quest cards.
10. Complete the card.
11. Confirm equipment remains locked until all active cards are complete.
12. Confirm the outcome story plays.
13. Confirm story rewards are applied.
14. Save and reload.
15. Confirm active, failed, completed, flags, and dialog choices persist.

## Debugging Tips

If a quest does not appear:

- Check `availability`.
- Check story flags.
- Check the quest has not already completed, failed, or expired.
- Check `data/overworld_quests.json` validates.

If a dialog does not appear:

- Check the active quest step.
- Check each choice `requires`.
- Check current stage ID.
- Check gold and gear requirements.

If a story does not play:

- Check the story ID exists in `data/stories.json`.
- Check all frame IDs exist in `data/frames.json`.
- Use the story editor validation.

If card art does not appear:

- Check the file path:
  `assets/GFX/overworld_quests/cards/<quest_id>.png`
- Check the quest ID spelling.
- Check the PNG loads outside the game.

If a board objective card does not appear:

- Check the quest is active.
- Check the current stage matches the objective `stage_id`.
- Check the objective is inside the active quest step.
- Check `board_objectives` is a list.

If a board objective never completes:

- Check the objective `stat_key`.
- Check `feedback` contains the same stat key.
- Check `win_reward_pairs.to_win` uses the same stat key.
- Check the objective type is currently supported.

## Current Known Limits

- Quest starts are intended to be wired through stories, but the exact story-start hook still needs final gameplay integration.
- Conditional dialog is functional but visually basic.
- Only `hold_piece_on_squares` has generic board-objective logic right now.
- Map quest markers are intentionally not built yet.

