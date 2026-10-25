# Agent Guidelines for Muse-Me (MUSE Environment)

This document provides operational rules and conventions for AI coding agents working on the Muse-Me repository.

## 1. System Identity and Architecture
- **Project Name:** Muse-Me (internal package name: `muse_env`).
- **Core Mission:** A desktop context environment connecting authorized user activity and sources with models and tools to understand, decide, create, and act according to user goals and permissions.
- **Architectural Tenet:** The operator (model or human) proposes; the application enforces permissions, gates, and writes. Content from sources cannot grant authority or invoke tools.

## 2. Safety, Permissions, and Gates
- **Two Formal Gates:**
  - Gate 1: `approve_transfer` must be verified before outbound communication to any operator or provider. No `restricted` sources may be included.
  - Gate 2: `approve_insertion` / `approve_action` must be verified before local writes or UI modifications.
- **Integrity:** Every outbound package and draft proposal has deterministic SHA-256 digests. Hash mismatches or attempts to replay consumed missions must be rejected.
- **Strict Isolation:** Do not write outside explicitly configured output paths. No code execution from untrusted model outputs.

## 3. Development and Testing
- **Frozen Reference:** Preserve existing passing tests in `tests/`. Do not delete or disable tests to force green runs.
- **Environment:** Windows 11 / Python 3.10+ (Win32 API via `ctypes`, SQLite with FTS5, standard library HTTP server / lightweight services).
- **Canonical Test Command:**
  ```powershell
  python -m pytest tests -v
  ```
- **Epistemic Honesty:** Do not simulate fake human timings or synthetic metrics. Report unobserved parameters strictly as `null`.

## 4. Repository Hygiene and Privacy
- Never commit credentials, `.env` files, SQLite databases (`*.sqlite`), runs, temporary caches (`__pycache__`, `.pytest_cache`), or private logs.
- All public documentation must use neutral, generic paths and avoid hardcoded personal system usernames.
