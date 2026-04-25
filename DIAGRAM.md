# Chess Quest System Diagram

## System Relationships

```text
main.py / ChessScreen
  |
  v
BootLoader
  |
  +--> Stockfish engine + EnemyMoveEngine
  +--> BoardManager
  +--> InputController
  +--> TurnController
  +--> GameResultManager
  +--> QuestInfo + QuestRewardHandler
  +--> Powers + CastSpells + SpellRules + SpellTargeting
  +--> Gear
  +--> MapChallenges
  +--> RenderPipeline + EffectsManager + AudioManager + AssetManager
  +--> GameWorld + StoryMode
```

## Match Flow

```text
setup_new_board()
  |
  +--> build board from player_army_fen
  +--> reset transient board/spell/power state
  +--> load stage assets
  +--> choose active quests
  +--> sprinkle gold
  |
  v
main loop
  |
  +--> InputController
  |     |
  |     +--> normal moves -> BoardManager -> QuestInfo
  |     +--> powers       -> Powers       -> QuestInfo
  |     +--> spells       -> SpellTargeting/CastSpells
  |     +--> gear         -> Gear
  |
  +--> TurnController
  |     |
  |     +--> EnemyMoveEngine
  |           |
  |           +--> MapChallenges.PreEngineMove()
  |           +--> Stockfish move / overrides
  |           +--> QuestInfo
  |           +--> QuestRewardHandler.post_piece_move_events()
  |
  +--> UIState + RenderPipeline + EffectsManager
  |
  v
GameResultManager
  |
  +--> win/loss/stalemate round
        |
        +--> QuestInfo.check_for_quest_win()
        +--> QuestRewardHandler.give_reward()
        |
        +--> fewer than 3 wins/losses
        |     |
        |     v
        |   reset_board()
        |
        +--> 3 wins/losses
              |
              +--> StoryMode win/loss story
              +--> GameWorld record win/loss
              +--> GameWorld overworld_move()
              +--> StoryMode new-level story
              v
            setup_new_board()
```

## Persistence Flow

```text
Persistent campaign state
  |
  +--> GameWorld.world_data / buildings / calendar / bank / tax
  +--> player_gold
  +--> powerups
  +--> gear inventory
  +--> spellbook_master
  +--> player_army_fen
  |
  v
Round setup copies/derives
  |
  +--> board position from player_army_fen
  +--> spellbook from spellbook_master
  +--> quest_status from active_quests
  +--> stage art from current world stage_id
```

## Rendering and Effects

```text
Game state on ChessScreen
  |
  +--> RenderPipeline
        |
        +--> BoardRenderer: board, pieces, targets, overlays
        +--> UIRenderMixin: portraits, powers, spells, gear, dialogs
        +--> magic effect runtime state
        +--> quest card / quest win animation
        |
        v
      EffectsManager
        |
        v
      ParticleSystem
```

## Data Sources

```text
data/quests.json
  -> QuestInfo
  -> quest cards, quest_status, rewards

data/spell_description.json
  -> AssetManager
  -> SpellRules / SpellTargeting / spellbook rendering

data/stories.json + data/frames.json
  -> StoryPlayer
  -> StoryMode rewards

assets/
  -> AssetManager / AudioManager / StoryPlayer
  -> rendering, audio, story media
```
