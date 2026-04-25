# Chess Quest — Agent Instructions

## Core Rule
Do NOT change game logic unless explicitly instructed.

This project contains custom mechanics layered on top of a chess engine.
Behavior that appears redundant may be intentional.

---

## Architecture Overview

- main.py → entry point
- engine/ → local Stockfish (do not modify)
- assets/ → excluded from repo (do not reference missing files)
- data/ → JSON game data + editors
- core systems:
  - spells
  - quest system
  - particle engine
  - UI rendering
  - game state management

---

## Repository Navigation

- Start with `ARCHITECTURE.md` for the current system map and module responsibilities.
- Use `DIAGRAM.md` for the high-level match lifecycle and system flow.
- Treat the code as authoritative if docs and code disagree.
- Do not modify game logic unless explicitly instructed.

---

## Development Rules

- Always preserve existing behavior unless explicitly told otherwise
- Prefer adding logging over modifying logic
- Do NOT remove or simplify conditionals without explanation
- Avoid large refactors unless explicitly requested
- Keep changes minimal and isolated

---

## Git Workflow Rules

- Assume work is happening on a feature branch
- Do NOT assume direct commits to main
- Suggest changes in small, reviewable chunks

---

## Safe Tasks

- Add logging
- Explain code
- Identify bugs
- Suggest improvements without applying them

---

## Dangerous Tasks (Require Explicit Permission)

- Refactoring core systems
- Modifying spell logic
- Changing quest reward behavior
- Altering game state transitions

---

## Notes

This is an experimental game with evolving mechanics.
Clarity and correctness are more important than code “cleanliness.”