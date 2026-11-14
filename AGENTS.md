# Instructions for AI coding agents

This file exists twice, with identical content: `AGENTS.md` (read by Codex) and `CLAUDE.md` (read by Claude Code). Change both in the same PR so they stay identical.

The team's plan of record is the *Crew Health Compass A-to-Z Execution Roadmap*. If a task prompt conflicts with this file, stop and ask your human.

Items marked ***Proposal*** were suggested by D and the team has not agreed to them yet. Follow them as defaults. Tell your human if a task conflicts with one. The team keeps or drops each proposal at G1.

## 1. Find your role first

- You work for one human team member. Your role and the files you may change come from **that human and their task prompt**. They do not come from which tool you are, or from whoever wrote this file.
- Before your first edit, state three things: which member you work for, their role, and which files this task lets you change. If you cannot tell, ask. Do not guess.
- The notes in section 7 apply only when you work for that member.

| Member | Role | Owns | Usual agent |
|---|---|---|---|
| A | Tech lead, analytics engine | `engine/`, `contracts/` | Codex |
| B | Data, health science, evaluation | `data/`, `catalogue/`, `eval/` | Codex |
| C | Frontend and UX | `frontend/` | Codex |
| D | Backend, security, data integrity, release | `api/`, `security/`, CI, deployment | Claude Code |

***Proposal:*** ownership not yet covered by the plan:

- `download/` (the NASA files uploaded at kickoff) belongs to B. Until B decides, no agent moves, renames, edits or deletes these files.
- `docs/` and the root docs (`README.md`, `AGENTS.md`, `CLAUDE.md`, `.gitignore`) belong to D.

**Edit only the files your role and task allow.** There are two exceptions:

- Anyone may add their own line to `docs/AI_USAGE.md`.
- During an integration window that A announces, you may edit the files A names.

If a task needs a change in another member's files, do not make it. Write down the change for that owner instead.

## 2. Rules for every role

1. Never commit or push to `main`. Work on your own branch. ***Proposal:*** name it `<member letter>-<topic>`, for example `a-contracts-v1`.
2. Keep each PR under about 300 changed lines, and include a summary.
3. Change contracts only through a PR labelled `contract-change` and approved by A.
4. Add no new dependency without approval. D checks its licence and known vulnerabilities.
5. Commit no secrets: no API keys, tokens, passwords or private keys. Real values go in `.env`. `.gitignore` only stops untracked files from being added by accident. It has no effect on files that are already tracked, `git add -f` overrides it, and it cannot see a secret pasted into an ordinary file. Check your diff before every commit.
6. Use no real personal data. Simulated data carries `provenance: simulated` and a visible **SIMULATED** label. A public dataset carries `provenance: dataset:<name>` and a citation.
7. Core health assessment must work offline without external AI APIs. Development, source retrieval, and deployment may use appropriate external services.
8. Take every health limit, rule and piece of guidance from `catalogue/indicators.yaml`, with a cited source. Never invent a medical threshold. If a source is missing, mark the rule as unresolved and tell your human.
9. Use honest wording in code, UI text and docs: "demo access control", "simulated data", "tested on our local prototype". Never write "secure", "compliant", "clinically validated", "production-ready" or "diagnosis".
10. Write code your human can explain. Nobody merges code they cannot explain.
11. Do not invent any item marked **TBD** in section 4. Ask your human.
12. ***Proposal:*** never weaken, skip or mock out a validation, role check or integrity check to make code run or a test pass. Report the problem instead.

## 3. How to run a task

Every task prompt should state: the goal, the allowed files, the files to read first, the acceptance tests, what is out of scope, and "return a PR under ~300 lines with a summary".

**Before you code,** read this file, then `contracts/` and `catalogue/indicators.yaml` once they exist.

**Before you open a PR:**

1. Rebase your branch onto the latest `origin/main`.
2. Run the checks for the code you touched. For Python, that means ruff and pytest. For the frontend, that means ESLint and the production build. Exact commands will be added here when CI is in place.
3. Add one line to `docs/AI_USAGE.md` with the tool, task, files and human reviewer.

## 4. Shared interfaces (frozen at G1, H2)

A owns these interfaces. Until G1, treat them as a draft.

- **Models** (in `contracts/`):
  - `Measurement {astronaut_id, indicator, value, unit, timestamp, provenance}`
  - `Flag {indicator, level, reason, rule_id, source_url, action, escalation}`
  - `SystemStatus {system, level, flags}`
- **Engine entry point:** `assess(measurements, history, catalogue)` returns statuses and flags.
- **Endpoints:**
  - `POST /measurements`: accept and validate a check-in
  - `GET /astronauts/{id}/status`: current system statuses and flags
  - `GET /astronauts/{id}/history?indicator=`: data for trend charts
  - `GET /catalogue`: units, measurement instructions, sources
  - `POST /demo/scenario`: load a labelled simulated scenario (demo mode only)
  - Added as scheduled: `POST /reports`, `POST /reports/verify`, `GET /audit/verify`
- **Body systems:** cardiovascular, sleep/behavioural, metabolic, thermal.
- **Levels:** green, amber, red.
- **`provenance` values:** `user`, `simulated`, `dataset:<name>`.
- **Demo access control (Planned):** every request carries a fixed demo token for one of two roles, astronaut or flight surgeon. The server uses the token for basic authentication (identifying the caller through the token) and authorization (checking what that caller may access). Always call this "demo access control". It is not production-ready account management. A token that is shared or publicly exposed does not establish a private user identity.
- **TBD at G1:**
  - the six indicators and the allowed units for each
  - the name of the role-token header, the demo token values, and which astronaut each astronaut token belongs to
  - the error format for refused values (HTTP 422 and the "data problem" result)
  - where plausibility checks live, and how the engine receives a "data problem" result
  - final confirmation of the folder layout

## 5. Branches, reviews and merging

- GitHub does not enforce branch protection on this repository, so people follow these rules by hand.
- Every two hours there is a DONE / NEXT / BLOCKED check-in. At each one, the team reviews PRs and runs CI and the end-to-end smoke test. A approves contract changes, and D merges approved PRs.
- A second human must review every change to the API, contracts or security code. ***Proposal:*** the same applies to CI files, `AGENTS.md`/`CLAUDE.md`, and dependency lists.
- Nobody merges unreviewed code during sleep shifts.
- Feature freeze is at H34: after that, only fixes. Code freeze is at H40: after that, only repairs to broken links or the deployment.

## 6. Security basics for all code (*Proposal*)

- Treat all input from the browser as untrusted. The API (`api/`) is the trust boundary.
- Use parameterised SQL queries only. Never build SQL by joining strings.
- Never use `eval`, `exec` or `pickle.load` on data from requests or files.
- Never print or log tokens or keys.
- Run security tests only against systems the team owns and runs locally, or against our own demo deployment.

## 7. Role notes (apply only when you work for that member)

### A: tech lead, analytics

- Hand off the JSON schemas and fixtures at H2, and `assess(measurements, history, catalogue)`.
- A approves contract changes and announces integration windows.

### B: data, health science, evaluation

- Hand off cited YAML rules, test datasets, scenarios and the evaluation report.
- B decides whether the project uses real data or simulation.

### C: frontend, UX

- Build screens against the fixtures first, then the API-integrated demo and the backup video.
- Show the SIMULATED banner whenever demo data is on screen.

### D: backend, security, release

- Hand off working endpoints, persistence, CI, local and public deployment, and the submission.
- D is a cybersecurity student who is new to backends, deployment and cryptography. Use plain English and define each technical term the first time it appears. Explain both *what* to do and *why*. Work in small steps that D can check, and confirm D understands before moving on.
- Keep security scope small. Do not add any of these: real accounts or passwords, OAuth or JWT refresh flows, self-managed HTTPS certificates, a WAF or SIEM, key vaults, mTLS, blockchain, differential privacy, or CORS (the API serves the frontend from the same origin, so CORS is not needed).
- D makes these decisions personally. Explain the trade-offs, but do not decide for D:
  - where the trust boundary is
  - what the hash chain proves and does not prove
  - where keys live and why they are not in the repo
  - what the role check actually blocks
  - the limits of encryption at rest when the key is on the same machine
- Do not commit, push or open PRs unless D asks.
