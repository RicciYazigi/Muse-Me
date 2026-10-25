# Agent Guidelines for Muse-Me (MUSE Environment)

This document provides operational rules and conventions for AI coding agents working on the Muse-Me repository.

## 0. Context Recovery and Continuity ("Entra en contexto")

At the start of each work session on Muse-Me, and whenever Ricardo says **«entra en contexto»**:
1. Open and read the local private memory root:
   `C:\Users\USER\Documents\ChatGPT\meta hackaton\muse-private-context\INDEX.md`
2. Read `INDEX.md` and `CURRENT_STATE.md` to identify the verified commit, current active task, and open limits.
3. Consult `TASKS.md` for active acceptance criteria, `DECISIONS.md` for valid architectural decisions, and pertinent session notes or reviews as needed.
4. If this local path is unavailable (e.g. running in an environment without access to Ricardo's local machine), report that fact honestly and recover context from public files (`docs/STATUS.md` and `README.md`); do not invent private memory contents. External collaborators are not required to have access to this private folder.

## 1. System Identity and Architecture
- **Project Name:** Muse-Me (internal package name: `muse_env`).
- **Core Mission:** A resident personal contextual assistant connecting authorized user activity and sources with models and tools to understand, decide, create, and act according to user goals and permissions.
- **Architectural Tenet:** The operator (model or human) proposes; the application enforces permissions, gates, and writes. Content from sources cannot grant authority or invoke tools.

## 2. Safety, Permissions, and Gates
- **Two Formal Gates:**
  - Gate 1: `approve_transfer` must be verified before outbound communication to any operator or provider. No `restricted` sources may be included.
  - Gate 2: `approve_insertion` / `approve_action` must be verified before local writes or UI modifications.
- **Integrity:** Every outbound package and draft proposal has deterministic SHA-256 digests. Hash mismatches or attempts to replay consumed missions must be rejected.
- **Strict Isolation:** Do not write outside explicitly configured output paths. No code execution from untrusted model outputs.

## 3. Development and Testing
- **Frozen Reference:** Preserve existing passing tests in `tests/`. Do not delete or disable tests to force green runs.
- **Environment:** Windows 11 / Python 3.10+ (Win32 API via `ctypes`, SQLite with FTS5, standard library HTTP server / lightweight services). CI verifies Windows and Ubuntu with Python 3.11, 3.12, and 3.13.
- **Canonical Test Command:**
  ```powershell
  python -m pytest tests -v
  ```
- **Epistemic Honesty:** Do not simulate fake human timings or synthetic metrics. Report unobserved parameters strictly as `null`.

## 4. Repository Hygiene and Privacy
- Never commit credentials, `.env` files, SQLite databases (`*.sqlite`), runs, temporary caches (`__pycache__`, `.pytest_cache`), or private logs.
- The private working context resides in `C:\Users\USER\Documents\ChatGPT\meta hackaton\muse-private-context` outside Git.
- All public documentation must use neutral, generic paths and avoid hardcoded personal system usernames.
