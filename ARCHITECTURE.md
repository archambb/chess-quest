# Chess Quest Architecture

This document describes the current code structure and observed runtime flow. It documents behavior supported by the code in this repository; unclear or fragile behavior is called out explicitly.

## Runtime Shell

### Entry Point and Boot

- `main.py` defines `ChessScreen`, initializes pygame, owns the shared game state object, and runs the main loop. Most behavior is delegated to manager/controller objects attached to `self`.
- `bootloader.py` builds the initial `ChessScreen` state: Stockfish engine, board defaults, powers, gear, assets, spell managers, quest managers, renderer, effects, map challenges, result manager, input, turn controller, debug controller, and menu.
- `config.py` contains screen sizing, board sizing, colors, magic-effect indexes, card scaling, gear order/descriptions, difficulty setting, and volume settings.
- `game_init.py` contains new-campaign initialization helpers for gold, army upkeep cost, player army FEN, and world economy state. The code exists, but `main.py` does not currently call it in the visible new-game path.
- `debug.py` grants debug spells, powerups, gear, and quest completion helpers.
- `debug_controller.py` handles debug input events.

Important state is stored directly on the `ChessScreen` object. Managers usually keep `self.g` as a reference to that shared object and mutate `g.board`, `g.powerups`, `g.quests`, `g.world`, and UI fields directly.

## Game State and Match Lifecycle

### Board and Round Setup

- `board_manager.py` owns board construction, match reset, move helpers, gold placement/collection, power timer decrementing, and player move finalization.
- `BoardManager.setup_new_board()` starts a new stage/tile battle. It resets stage score (`current_state_wins`, `current_state_losses`), turn count, player side, board contents, transient board effects, selected UI state, spellbook from `spellbook_master`, active quests, background/portrait/piece assets, quest selection, and board gold.
- `BoardManager.reset_board()` starts the next round within the same stage. It restarts Stockfish, clears move/effect/selection state, reloads spellbook from `spellbook_master`, resets quest status tracking for the already-selected active quests, alternates player side with stage exceptions, reapplies the player army, sprinkles gold, applies certain pending quest reward flags, and lets the AI make the opening move when the player is black.
- `engine.py` wraps the enemy Stockfish move flow. It sanitizes board state, chooses a move using difficulty, map effects, greed/magnet/recovery/mirror overrides, pushes the move, applies enemy post-move effects, updates quests, clears king protections, increments completed turns, and unlocks powers after 10 completed turns.
- `turn_controller.py` advances enemy turns from the main loop. It calls the enemy engine when it is not the player turn, decrements shield/freeze/magnet timers after an enemy move, and runs `QuestRewardHandler.post_piece_move_events()`.
- `game_result.py` owns terminal-state handling. It converts checkmate/stalemate/rage-quit into win/loss/stalemate round handlers, updates quest variables, checks quest wins, increments win/loss counters, and advances the overworld after 3 wins or 3 losses.
- `difficulty.py` computes and applies Stockfish skill levels from configured difficulty and number of worlds beaten.

### Player Input

- `input_controller.py` handles hover state, menu interception, power icon clicks, time warp, spellbook clicks, gear targeting, board-targeted powers, spell targeting, swaps, piece selection, and normal move attempts.
- `menu.py` draws and handles the in-game menu. Save/load/exit-to-main callbacks currently print or show not-implemented feedback.
- `ui_state.py` manages hard pauses, feedback scroll messages, check overlay triggering, and enemy dialog text.

### Round and Stage Rules

- `map_challenges.py` contains stage-specific board effects. It runs `PreEngineMove()` before enemy moves, prunes legal player moves for certain stages, applies slip after player moves, manages stage-specific state like lava rows, stalker, astral gate, shields/freezes, resurrections, promotions, and enemy economy effects.
- `game_world.py` owns the 4x4 overworld, stage metadata, tile states, building choices, calendar/month advance, bank/tax state, and movement between lands.
- `game_world_render.py` renders and handles the overworld UI.
- `game_won.py` displays the territory win/building selection UI after a tile is beaten.

## Spells and Powers

### Powers

- `powers.py` validates and applies inventory powerups: bombs, freezes, shields, advanced shields, swaps, promotions, magnets, and several spell-backed power actions. Most powers are restricted to the player's half of the board and often contain safety checks to avoid creating illegal king attacks.
- `Powers.initialize_empty_powerups()` creates the canonical powerup inventory keys and loads power icons.
- Power use is gated by `g.powers_unlocked` except for spellbook-powered actions. `BoardManager._relock_powers()` resets this gate at board setup/reset. Gear key and turn progression can unlock it.

### Spells

- `cast_spells.py` implements spell effects such as Flood, Summon Elf, Summon Undead Elves, Ice Blast, Wind Storm, Desert Sun, Inspire Soldier, Orb of Premonition, Heal Pawns, Sacrifice, One With Light, Greed, Meteor Shower, Granite Elf, and Mirror Armies.
- `spell_rules.py` evaluates whether spells should be available in the spellbook UI.
- `spell_targeting.py` arms spellbook choices, builds target highlight lists, handles targeted spell board clicks, and routes instant spells to `CastSpells`.
- `data/spell_description.json` defines spell display metadata, descriptions, cast type, target mode, and target highlight color.

Spellbook persistence is split:

- `spellbook_master` is the persistent learned-spell list.
- `spellbook` is the current round/stage working list, reset from `spellbook_master` in board setup/reset.
- Individual spell casts usually remove the spell from `spellbook`, not from `spellbook_master`.

## Quest System and Rewards

- `quest_info.py` loads `data/quests.json`, presents quest selection, tracks active quests, initializes `quest_status`, updates quest stats from moves/powers/game state, checks quest win conditions, triggers quest win animations, and delegates rewards.
- `quest_cards.py` builds quest card images from quest data.
- `quest_rewards.py` applies quest rewards and queues reward presentation state. Rewards can grant gold, grant powerups, refresh spells, mutate the board, freeze pieces, set future-match flags, set persistent quest flags, or trigger visual/audio effects.
- `tool_quest_validation.py` and `tools/tool_quest_validation.py` are quest JSON/editor validation utilities.
- `data/quests.json` is the quest content source. Each quest has `quest_number`, `title`, `rules`, `feedback`, and one or more `win_reward_pairs`.
- `quest reward validation.txt`, `quest trigger validation.txt`, and `QA Quest List.txt` are validation/reference notes, not runtime code.

Quest evaluation happens from several places:

- Player moves and enemy moves call `QuestInfo.update_quest_variables(...)`.
- Power use calls `update_quest_variables(..., power_used=...)`.
- Round-end handlers call pieceless updates and `check_for_quest_win()`.
- `QuestInfo.check_for_quest_win()` compares `quest_status` against JSON `to_win` requirements and calls `win_quest()` when a reward pair is satisfied.

Important reset behavior:

- `setup_new_board()` clears `active_quests` before showing quest selection.
- `reset_board()` keeps the selected active quests but resets `quest_status` via `setup_quest_status_tracking()`.
- `QuestInfo.reset_quest_variables()` clears many quest runtime trackers and temporary flags when a stage is fully won, while preserving `enable_reflective_shield` and `enable_empowered_freeze` according to its comment and implementation.

## Inventory, Gear, Economy, and Progression

### Gear

- `gear.py` owns non-consumable gear inventory and gear actions. It uses `config.GEAR_ORDER` and `config.GEAR_DESCRIPTIONS`.
- Gear can mutate board state, arm pending board-click targets, unlock powerups, provide a mating hint, or alter enemy pieces.
- Gear usage is routed from `RenderPipeline.handle_gear_click()`. The renderer only allows gear clicks when there are no active quests.
- Debug mode grants all gear via `Debug_GiveAllGear()`.

### Gold and Powerup Inventory

- `BoardManager.sprinkle_gold_pieces()` places 5 gold squares each board setup/reset.
- `BoardManager.collect_gold()` increments `g.player_gold` when a player piece stands on a gold square.
- `market.py` lets the player buy powerups with `player_gold`; prices have stage overrides.
- Quest rewards, story rewards, and market purchases all mutate `g.powerups` and/or `g.player_gold`.

### Army and Buildings

- `army_upkeep.py` runs monthly upkeep. It lets the player pay to keep non-king army pieces and writes the resulting 2-rank army FEN back to `g.player_army_fen`.
- `training.py` renders army boards and implements training-center restoration/upgrades. Training can write a trained army FEN back to `g.player_army_fen`.
- `bank.py` manages deposit/withdraw UI and stores bank balance on `GameWorld`.
- `tax_office.py` manages tax office UI and uses tax fields on `GameWorld`.
- `GameWorld._advance_month()` applies army upkeep/training, bank interest, and tax income whenever the player moves to a new land.

## Rendering, Effects, Audio, and Assets

- `render.py` defines `RenderPipeline`, which combines board rendering and UI rendering, draws the main scene, quest selection, piece animations, gold drops, spellbook, quest cards, reward/quest win animation, magic effects, particles, feedback, and menu overlay.
- `render_board.py` draws the board, selectable/highlighted squares, power/spell/gear target overlays, status square overlays, astral/compass hints, meteor quadrant overlays, and screen overlays.
- `render_ui.py` draws the background, power/spell side panel, lock overlay, portraits, enemy dialog, game-state images, feedback scroll, quest status scroll, and menu overlay.
- `effects.py` wraps the particle system and exposes reward effect helpers.
- `particle.py` is a general pygame particle engine with image registration, emitters, physics, animation modes, and a demo harness.
- `assetmanager.py` loads piece art, portraits, backgrounds, spellbook art, gear icons, power icons, gold coins, magic effects, lock UI art, and game-state images.
- `audio.py` loads SFX/music/voice assets and exposes play, random-prefix play, volume update, stage voice, and stage music helpers.
- `ui_theme.py` contains small UI drawing/color helper functions.

## Story and Narrative

- `story_mode.py` maps stage IDs to story IDs, invokes `StoryPlayer`, and applies story rewards to powerups and spells.
- `play_story.py` loads `data/stories.json` and `data/frames.json`, plays story frames, assets, music/voice, and options.
- `intro_screen.py`, `book_reader.py`, and empty placeholder modules `library.py`, `menu_screen.py`, and `movie_player.py` support or reserve space for non-match UI.
- `data/stories.json` maps story IDs to frame sequences.
- `data/frames.json` contains frame text/options/rewards.

## Tools, Editors, and Non-Core Files

- `data/quest_editor.py` and `data/story_editor.py` are editor utilities.
- `tool_spritesheet_viewer.py`, `tool_build_water_spritesheet_test.py`, and matching files under `tools/` are asset/development tools.
- `tools/sora_prompter.py`, `tools/story_image_prompts.json`, `tools/file_packager.py`, and `tools/line_counter.py` are development utilities.
- `data/backup/` contains historical story/frame/editor backups.
- `archive/` contains old zipped snapshots and pre-fix copies of spell/input/power modules; these are not referenced by the live imports.
- `legacy/` contains empty legacy Python placeholders and an old planning image.
- `git_notes/commands.txt` and `.vscode/launch.json` are local development support files.
- Text files such as `Design Doc.txt`, `equipment_design.txt`, `game_world_state_driving.txt`, `overworld order.txt`, `to_do.txt`, `bug_report.txt`, and validation notes are design/reference notes.

## Single Match Lifecycle

1. Boot creates `ChessScreen`, loads managers/assets, starts Stockfish, then creates a `GameWorld`.
2. `setup_new_board()` initializes a stage battle, loads stage art, resets transient match state, resets `spellbook` from `spellbook_master`, asks the player to choose quests, and places gold.
3. The main loop repeatedly handles hard pause, hover/input, terminal state processing, enemy turn progression, UI state, and rendering.
4. Player actions are routed through `InputController` to board moves, powers, spells, or gear. Successful player moves update quests, clear king protections, collect gold, increment `g.turns`, and may trigger map-challenge side effects.
5. Enemy turns are routed through `TurnController` and `EnemyMoveEngine`. The engine applies map pre-move effects, chooses/pushes a move, applies enemy post-move effects, updates quests, clears king protections, increments completed turns, and may unlock powers after 10 completed turns.
6. `GameResultManager.process_terminal_state_if_needed()` detects checkmate/stalemate/rage quit and calls win/loss/stalemate round handlers.
7. Round-end handlers update terminal quests, run `between_rounds_quest_activity()`, check quest wins/rewards, increment player win/loss counters, and either reset the board for another round or advance the overworld after 3 wins/losses.
8. After 3 wins, quest variables are reset, win story can run, the world records the tile as won, building selection may open, the overworld movement loop runs, new-level story may run, then `setup_new_board()` starts the next battle.
9. After 3 losses, loss story can run, the world records a loss, overworld movement runs, new-level story may run, then `setup_new_board()` starts the next battle.

## Reset vs Persist

### Reset Between Rounds

- Board position is rebuilt from `player_army_fen`.
- Move history, frozen squares, shielded squares, magnet square, selected piece/power/spell, boulders, completed turn count, and spell availability cache are reset.
- `spellbook` is reset from `spellbook_master`.
- Quest status counters are reinitialized for the already-selected active quests.
- Powers are relocked via `_relock_powers()`.
- Gold-on-board is cleared and re-sprinkled.
- Stockfish is quit and relaunched.

### Reset On New Stage Battle

- Active quests are cleared and the player chooses new quests.
- Current stage win/loss counters are reset.
- Background, portrait, and piece images are loaded for the new stage.
- Many quest runtime variables are reset after fully winning a stage via `reset_quest_variables()`.

### Persist Across Rounds or Stages

- `player_gold` persists unless spent/earned.
- `powerups` persist unless used or granted.
- `gear` inventory is non-consumable and persists in memory.
- `spellbook_master` persists learned spells; `spellbook` is the per-round copy.
- `player_army_fen` persists and is used to rebuild each board.
- `world.world_data`, building choices, bank balance, tax office balance, calendar, and visits persist in memory.
- Some quest reward flags intentionally persist until consumed by later setup/reset logic, such as `set_outer_pawns_as_rooks`, `enable_knightmare_mode`, and `enable_no_future_rooks`.
- `enable_reflective_shield` and `enable_empowered_freeze` are not cleared by `QuestInfo.reset_quest_variables()`.

## Unclear or Fragile Areas

- `StoryMode.handle_new_level_story()` reads `losses`, while `GameWorld.record_loss()` writes `lose`.
- `QuestInfo.update_quest_variables()` is large and contains many quest-specific branches; several branches depend on state fields that are set elsewhere and not all are reset in one place.
- `game_init.py` documents new-game setup, but the visible boot/new-game path does not clearly invoke `apply_new_game_settings()`.
- Several modules contain placeholder or TODO behavior (`trigger_firewall`, `Wand of Stupidity`, save/load, final boss, empty modules).
