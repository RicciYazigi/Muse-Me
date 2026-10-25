# Muse-Me

> **MUSE Environment (Muse-Me):** A contextual assistance environment that connects authorized user activity, project memory, models, and tools to help understand, decide, create, and act according to user goals and permissions.

---

## 1. Vision and Problem Statement

Modern knowledge work is fragmented across documents, code editors, communication apps, and browsers. Existing AI assistants either:
1. Lack contextual awareness beyond the current chat window.
2. Silently ingest background desktop activity without granular user authorization or provenance verification.

**Muse-Me** solves this with an auditable, human-in-the-loop desktop environment:
- **Zero Surprises / Policy-Enforced Gates:** The operator (model or human) proposes; the application enforces permissions, cryptographic gates, and local writes. Content from an observed source can never grant itself permissions or trigger tools.
- **Two Distinct Core Capabilities on One Engine:**
  - **Evidence Comparison:** Analyzes authorized sources to answer queries, highlighting contradictions and citing exact source digests without prematurely favoring the newest document.
  - **Deliverable Production:** Generates briefs, reports, or plans in Markdown, enforces a two-gate authorization cycle, performs exact local file creation, and verifies contents via cryptographic readback checks.
- **Persistent Project Memory:** Retains missions, checkpoints, and source revisions using local SQLite/FTS5 storage. Detects stale context when source files change.

---

## 2. Architecture and Data Flow

```
Authorized Sources ──► Relevant Context ──► User Intent / Capability
                                                    │
                                                    ▼
Memory / Ledger  ◄── Verification ◄── Local Action ◄── Gate 2 (Insertion) ◄── Operator Proposal ◄── Gate 1 (Transfer)
```

1. **Gate 1 (`approve_transfer`):** Cryptographically binds the prompt and selected context into a deterministic `request.json` package. Excludes any `restricted` sources before outbound transmission.
2. **Operator:** Generates a structured proposal (`response.json`) bound to the exact request hash and citations.
3. **Gate 2 (`approve_insertion` / `approve_action`):** The human operator inspects the proposed draft. Once approved, the exact artifact is written to the authorized target directory or inserted into the native surface.
4. **Verification & Ledger:** The system performs a readback check (hashing written files or issuing `WM_GETTEXT` on Win32 controls), records the entry into an immutable ledger, and marks the mission consumed to prevent replay attacks.

---

## 3. Current Core Capabilities

| Capability | Purpose | Gate Verification | Readback Check |
| :--- | :--- | :--- | :--- |
| **Evidence Comparison** | Cross-source synthesis, contradiction detection, and citation audit. | Gate 1 (Transfer) | Semantic & source hash validation |
| **Deliverable Production** | Markdown brief, report, or specification generation. | Gate 1 + Gate 2 (Insertion) | SHA-256 file readback check |
| **Project Memory** | Multi-project isolation, FTS5 lexical retrieval, revision tracking, and change invalidation. | Checkpoint validation | Ledger chain verification |
| **Win32 Native Surface** | Opt-in read-only observation and direct control insertion via Win32 API. | HWND/PID binding + Gate 2 | `WM_GETTEXT` verification |

---

## 4. Installation and Setup

### Prerequisites
- Python 3.10+ (tested on Python 3.11, 3.12, 3.13)
- Windows 11 / 10 for native Win32 controls and observation (cross-platform core runs on Linux/macOS)

### Install Dependencies
```bash
# Clone the repository
git clone https://github.com/RicciYazigi/Muse-Me.git
cd Muse-Me

# Install package and development tools
pip install -e ".[dev]"
```

### Configuration (Optional Meta / Llama API)
Copy the example environment file and configure your API credentials if using real cloud inference:
```bash
cp .env.example .env
```
If `.env` is absent or `MODEL_API_KEY` is not set, Muse-Me automatically operates in **Assisted Operator** or **Reproducible Demonstration** mode with explicit visual labeling.

---

## 5. Quickstart and Demonstration

### Unified Local Review Panel
Launch the local review interface (running locally on `http://127.0.0.1:8080`):
```powershell
python run_panel.py
```
*On Windows, you can also run `.\Start-ReviewPanel.ps1` or double-click `ABRIR_PANEL.cmd`.*

### Project Memory CLI Demonstration
Run the multi-project synthetic scenario suite:
```powershell
python demo_projects.py
```
This demonstrates project isolation, full-text retrieval, change detection upon file re-ingestion, and automatic invalidation of stale checkpoints across 4 diverse scenarios.

### Assisted Native Win32 Flow
Execute an end-to-end mission inserting directly into a real Win32 `EDIT` control:
```powershell
python run_operator_assisted_flow.py
```

---

## 6. Testing and Verification

Run the comprehensive automated test suite (85 tests covering core logic, double gates, tamper-evident ledger, memory, and surfaces):
```bash
python -m pytest tests -v
```

### Continuous Integration (CI)
GitHub Actions verifies every push across:
- **Windows:** Validates all 85 tests including Win32 native controls, cryptographic anchors, and regression invariants.
- **Linux:** Validates 72 tests covering context building, project memory, gate authorization, and cryptography, cleanly skipping 13 Win32-specific desktop tests (72 passed, 13 skipped).

---

## 7. Meta API Status and Epistemic Limits

- **Meta Adapter:** An integration adapter (`src/muse_env/providers/meta.py`) connects to Llama API endpoints. When valid credentials exist in `.env`, it issues bounded requests and logs prompt/response digests.
- **Epistemic Honesty:** When running without active API keys, the system explicitly marks mode as `assisted_operator` or `fixture_demo`. It **never** fabricates AI responses, latency figures, or human effort metrics. Unobserved measurements are strictly reported as `null`.
- **Sandbox Boundary:** Temporary directories and file writes are confined strictly to authorized target folders. Muse-Me does not execute arbitrary code generated by models.

---

## 8. Spanish Summary / Resumen en Español

**Muse-Me** es un entorno de escritorio auditable para asistencia contextual con modelos de IA. Permite comparar evidencia documental y generar entregables locales bajo un modelo de doble autorización (Compuerta 1 para transferencia de contexto sin datos restringidos; Compuerta 2 para aprobación de contenido antes de su escritura local). Incluye memoria de proyectos con SQLite FTS5, detección de cambios en archivos fuente y controles nativos Win32 con comprobación criptográfica de integridad.
