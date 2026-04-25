# Chess Quest (this file generated with AI for now until closer to finished project)

Chess Quest is a fantasy RPG built on top of a traditional chess engine, blending classic strategy with spells, quests, progression systems, and dynamic game mechanics.

Instead of playing standard chess, players engage in a modified battlefield where abilities, effects, and game state transformations change how each match unfolds.

---

## Core Features

* Custom game mechanics layered over a chess engine
* Spell and ability system (freeze, lightning, movement effects, etc.)
* Quest system with dynamic win conditions and rewards
* Particle and visual effects engine
* Story and progression elements
* Modular architecture for expanding mechanics

---

## Requirements

* Python 3.10+ (recommended)
* Dependencies listed in `requirements.txt` (if applicable)

---

## Stockfish Engine (Required)

Chess Quest uses the Stockfish chess engine for move calculation.

Stockfish is **not included** in this repository.

### Setup

1. Download Stockfish from: https://stockfishchess.org/download/
2. Extract the binary
3. Place it in:

```
/engine/stockfish/
```

4. Update any paths in `config.py` if needed

---

## How to Run

```
python main.py
```

Depending on your setup, you may need:

```
python3 main.py
```

---

## Project Structure (Simplified)

```
chessquest/
│
├── main.py
├── config.py
├── engine/           # (ignored) local Stockfish install
├── assets/           # (ignored) large game assets
├── data/             # game data, JSON configs, editors
├── tools/            # utilities and dev tools
├── *.py              # core game systems
```

---

## Assets

Game assets (images, audio, etc.) are not included in this repository due to size and licensing considerations.

They may be distributed separately or bundled with releases.

---

## Development Status

This project is actively in development. Systems may be incomplete, experimental, or subject to change.

---

## License

This project is licensed under the GNU General Public License v3.0.

You are free to:

* Use
* Modify
* Distribute

Under the condition that:

* Any derivative work must also be licensed under GPL v3
* Source code must be made available

See the LICENSE file for full details.

---

## Contributing

Contributions, ideas, and feedback are welcome.

---

## Notes

* This project intentionally separates code from large assets
* External dependencies (like Stockfish) must be installed manually
* Expect rapid iteration and evolving architecture
