# Muse-Me

A personal assistant that understands the work you choose to share with it.

I started Muse-Me because I kept moving between code, documents and conversations, then explaining the same context again in each AI chat. I want an assistant I can call while working: one that can bring together the relevant information and help me do something with it.

The goal is to follow activity in selected applications with permission, maintain a temporary working memory and prepare useful help in the background. When called, Muse-Me should offer concrete options based on the task: compare conflicting information, gather references, draft a revision or prepare an action for review. Project continuity is one use case; the same approach could support creative work, research and operations.

**This repository is an experimental foundation for that experience. The resident assistant and live Meta integration are still being built.**

## What works today

- A local review panel with project memory, source selection and permission controls.
- SQLite/FTS5 retrieval, source revisions and persistent mission checkpoints.
- Controlled Windows observation and insertion, tested with native Win32 EDIT controls. Compatibility with arbitrary desktop applications has not been established.
- A file-based assisted operator workflow: export a request, import a proposal, review it and verify insertion by reading the target back.
- Deterministic evidence comparison and Markdown generation. These currently use rules and templates, not model reasoning.
- A small MCP stdio interface for context packages and proposal operations. It is an entry point to the environment, not the whole product.
- Experimental temporal containment using a vendored Fuse core, connected to selected write and insertion paths.

## Try the existing prototype

Use Windows for the native desktop workflows. CI currently covers Windows and Ubuntu with Python 3.11, 3.12 and 3.13. The package declares Python 3.10+, but 3.10 and macOS are not covered by that CI matrix.

```powershell
git clone https://github.com/RicciYazigi/Muse-Me.git
cd Muse-Me
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe run_panel.py
```

The panel starts on loopback, normally port 8080, and opens a browser. It creates controlled demonstration windows on Windows. These are test surfaces, not automatic access to all your applications.

For a deterministic console demonstration:

```powershell
.\.venv\Scripts\python.exe demo_projects.py
.\.venv\Scripts\python.exe demo_muse_me.py
```

These scripts write local demo data. `demo_muse_me.py` resets its own demonstration database and creates synthetic sources and an output artifact. Use a separate checkout for demos. No Meta key is required, and their output is not a measurement of AI quality or human productivity.

## Meta integration

The text HTTP adapter lives in `src/muse_env/providers.py`. It reads `MODEL_API_KEY` from the process environment. The repository does not automatically load `.env` files. The provider's endpoint and model defaults still need to be verified against the API available to the hackathon account.

The panel currently uses the assisted operator workflow; setting a key does not switch its comparison and report capabilities to Meta inference. Its connection indicator can also mislabel configured credentials as connected. A live Meta request has not been independently demonstrated for the reviewed version.

The next increment will connect real inference to authorized context and retain the original request and response for evaluation.

## Fuse's role

[Fuse AI](https://github.com/RicciYazigi/fuse-ai) accumulates externally supplied risk scores over a trajectory. Muse-Me uses a vendored core from the FuseGate edition through `TrajectorySensor`.

The controller can permit authorized actions, restrict mutations in DEGRADE, or stop actions in STOP. The panel's default sensor uses thresholds 0.02 / 0.04; an explicitly supplied default `GatePolicy` uses 0.04 / 0.08. This configuration difference needs consolidation.

Current panel signals include a fixed insertion score and permission-based heuristics. The integration tests exercise the controller; they do not establish reliable detection of harmful desktop activity. Fuse can restrict an action, but it cannot grant permission.

## Evidence and limits

A separate local review of commit `2f0b3dd3ab0302e6787d410430ddff1f46372864` reproduced **92 passing tests on Windows/Python 3.13**, with no failures or skips. [CI for that commit](https://github.com/RicciYazigi/Muse-Me/actions/runs/40162257110) also completed successfully.

```powershell
.\.venv\Scripts\python.exe -m pytest tests -v
```

Passing tests are not a security certification. The reviewed version still has known gaps involving relative output paths, deleted sources served through MCP, and persistent approvals bound to the exact operation and destination. Use the prototype with non-sensitive test data and controlled targets while those routes are corrected.

The ledger and content hashes support integrity checks; they are not immutable storage, signatures or proof that a claim is true. External anchors require a separately trusted reference. The historical utility pilot demonstrates transport and verification; independent generation for its recorded condition B was not established, and no human productivity improvement has been demonstrated.

## What comes next

1. Close the known execution and source-freshness defects.
2. Connect real Meta inference with visible errors and recorded inputs and outputs.
3. Build a resident activity-to-assistance loop across two authorized applications.
4. Separate observation intensity, inference budget and action permissions.
5. Evaluate useful results, user effort, interruptions and cost against the same model with manually assembled context.

Temporary memory, confirmed long-term preferences, automation suggestions and specialized agents belong to that direction. Multiuser collaboration is future work, not an implemented feature.

## Repository map

- `src/muse_env/`: memory, context, operators, controls and panel.
- `tests/`: automated checks and regression cases.
- `experiments/utility_pilot/`: historical experimental harness, not proof of comparative benefit.
- `demo_projects.py` and `demo_muse_me.py`: synthetic demonstrations.
- `docs/`: design and historical reports. Several documents still describe earlier stages and need reconciliation with the reviewed state above.

The vendored Fuse code retains its own license under `src/muse_env/_fusible_vendor/LICENSE`. This does not specify licensing for the rest of the repository, which currently has no root license file.

## En español

Muse-Me busca acompañar el trabajo que autorizas a observar y ofrecer ayuda concreta cuando lo llamas. Esta versión contiene parte de la memoria, el panel y los controles necesarios; todavía falta convertirlos en una experiencia residente con modelos Meta reales. Las demostraciones actuales verifican mecanismos y no deben confundirse con un asistente terminado.
