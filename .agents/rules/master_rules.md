---
trigger: always_on
---

# Project: GnomeThemeManager
# Type: Python 3.10+ / GTK4 / Libadwaita application
# Mode: VIBE CODING (user reviews only, never writes code)

## Absolute Rules

1. NEVER modify architecture without explicit approval.
2. ALL logic in `src/gnome_theme_manager/core/` only. GUI and CLI must consume the same APIs.
3. NEVER add dependencies beyond PyGObject and `requests` (only in Phase 3+).
4. ALL new modules must have type hints (PEP 484) and pass `mypy --strict`.
5. NEVER use `print()` in `core/` or `gui_gtk/`. Use `logging` module.
6. NEVER store app state in `~/.config/` — use `~/.local/state/gnome-theme-manager/`.
7. Target: Ubuntu 24.04 + GNOME 46. Test commands must work on this stack.

## i18n Rule (hard rule)
- New user-visible strings => gettext `_()` + po/en.po + po/it.po updated
  in the SAME commit as the feature. Never defer translations to phase close.

## STOP Conditions (hard rule)
- Any failure in $TEST_SUITE, $LINT_CMD, $TYPE_CHECK_CMD, or a crash in
  $GUI_LAUNCH_CMD = HARD STOP. No new branches, no new commits, no next tasks.
- A task is committable ONLY when all four canonical commands are green.
- "Fix without confirmation" = fix the failure autonomously, never skip it.

## Testing Requirements

- pytest coverage ≥ 80% on `core/`
- Tests must be deterministic and isolated (use `tmp_path` fixtures)
- CLI exit codes: 0=success, 1=generic error, 2=bad usage, 3=permission error

## File Conventions

- Modules: snake_case
- Classes: PascalCase
- Constants: UPPER_SNAKE_CASE
- Branches: feature/phase-N-slug

## Commit Policy

- 1 task completed + tested = exactly 1 commit (code + tests ONLY)
- Phase closure commit contains ONLY docs/i18n/verification changes
- NEVER execute commits yourself: print the command, the user executes it
- Per-task commits use explicit `git add <files>`, never `git add -A`
- Message format: feat(scope): task X.Y — description

## Current Phase Reference

Before any task, read `docs/MASTER_PLAN.md` to understand current phase and tasks.