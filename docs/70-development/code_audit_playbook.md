# Code-base Audit Playbook

This playbook describes a **step-by-step, tool-assisted procedure** for
inventorying, triaging and planning cleanup work on a large Python
monorepo (like Praxis).  It is written at a level of detail that a junior
developer *or* a less-capable LLM agent can execute without further
clarification.

> **Scope** – The examples assume the repository layout used by Praxis
> (backend / frontend / workbench), but the same commands work for any
> Git project as long as you adjust the path prefixes.

--------------------------------------------------------------------
🔖 Legend used in the instructions
--------------------------------------------------------------------
| Symbol | Meaning                               |
|--------|---------------------------------------|
| `$`    | run in a POSIX shell (bash, zsh, …)   |
| `▶`    | manual action / copy-paste something  |
| `☑`    | checkbox you tick once the step done  |

--------------------------------------------------------------------
PHASE 0 – Ground rules             (~30 min)
--------------------------------------------------------------------
0-1  ☑ **Freeze new feature work** during the inventory period.

0-2  ☑ **Adopt a single CSV file as the source-of-truth** for the audit
     (no cloud spreadsheet).  All manipulations will be done with
     Python & pandas so the workflow stays local and version-controlled.

`audit_master.csv` initial columns:

```
path,component,type,loc,churn,flags,
# ───────────────────────────── domain restructuring ─────────────────────────
current_folder,ideal_folder,ideal_filename,
# ───────────────────────────── evaluation results ───────────────────────────
disposition,arch_notes,impl_notes
```

*You can add more columns later—pandas doesn’t care.*

0-3  ☑ Define an *ignore pattern* for generated artefacts.  Example:

```
docs/**
artifacts/**
*.json
*.lock
```

Store it in `tmp_audit_ignore.txt`; later commands will reference it.

--------------------------------------------------------------------
PHASE 1 – Automated inventory             (~½ day)
--------------------------------------------------------------------

1-1  ☑ **Collect raw file list**

```bash
$ git ls-files > all_files_raw.txt
$ grep -v -f tmp_audit_ignore.txt all_files_raw.txt > all_files.txt
```

1-2  ☑ **Count lines of code** – install *cloc* if missing.

```bash
$ cloc --by-file --csv --quiet backend frontend workbench \
      > cloc_by_file.csv
```

1-3  ☑ **Compute Git churn (touch count)**

```bash
$ git log --name-only --pretty=format: | \
  grep -v -f tmp_audit_ignore.txt | sort | uniq -c | \
  awk '{print $2","$1}' > git_churn.csv
```

1-4  ☑ **Run *vulture* for dead-code analysis.** (Already in our
     dev-dependencies.)

```bash
$ vulture backend/src > vulture_raw.txt || true
```

--------------------------------------------------------------------
PHASE 2 – Merge metrics into the spreadsheet             (~1 hour)
--------------------------------------------------------------------

We will create **`audit_master.csv` entirely with pandas** and keep it in
version control.  Exact snippet (copy-paste):

```python
import pandas as pd

# --- load raw metrics ------------------------------------------------------
loc   = pd.read_csv("cloc_by_file.csv")              # path,loc,code,comment …
churn = pd.read_csv("git_churn.csv", names=["path", "churn"])

# --- merge & initialise extra columns -------------------------------------
df = loc.merge(churn, on="path", how="left").fillna({"churn": 0})

for col in (
    "component","type","flags",
    "current_folder","ideal_folder","ideal_filename",
    "disposition","arch_notes","impl_notes"
):
    df[col] = ""    # will be filled during triage

# helper: derive current_folder automatically
df["current_folder"] = df["path"].str.rpartition("/")[0]

df.to_csv("audit_master.csv", index=False)
print("Created audit_master.csv with", len(df), "rows")
```

Result: every file already has **path / loc / churn / current_folder**;
the rest are blanks to be completed in the following phases.

--------------------------------------------------------------------
PHASE 3 – First-pass categorisation             (~½ day)
--------------------------------------------------------------------

For each row you now fill **component** and **type** with these enums:

```
type: code | test | doc | fixture | scratch | generated | vendored
Mandatory values to fill during this phase:

```
component   : core-backend | plugins | cli | tests | docs | frontend | workbench
type        : code | test | doc | fixture | scratch | generated | vendored
flags       : generated, vendored, deprecated, todo-heavy (comma-sep)
ideal_folder / ideal_filename : leave blank if same as current
```
```

Tips:
* Use directory naming to bulk-fill (Sheets filter by `path contains`).
* Mark obvious junk (`debug_*.py`, `trace_*.md`) as `scratch`.

--------------------------------------------------------------------
PHASE 4 – Manual triage walk-through             (~1 week for 10 kLOC)
--------------------------------------------------------------------

4-1  Sort the sheet by **loc × churn** descending (largest & most
     changed first).

4-2  For each file (or logical group):

```
▶  open the file in editor.
▶  Answer **seven** questions and record directly into the row:

```
arch_notes      : bullet answers to Q1-3
impl_notes      : bullet answers to Q4-5
ideal_folder    : if different, propose folder (e.g. plugins/core/agent)
ideal_filename  : if rename makes sense (snake_case, remove "debug_")
disposition     : KEEP | RENAME | MERGE | DELETE | REWRITE
```

Questions checklist (copy-paste into `arch_notes` / `impl_notes`):

1. Single clear responsibility?  (Y/N)
2. Overlap / duplicate with other file(s)?  list paths or "No".
3. Correct layer / package for Domain Driven Design?  (core/app/plugin…)
4. Imported in production path?  (`git grep module_name`)  (Y/N)
5. Unit-tests exist?  (Y/N)
6. Name reflects purpose?  (Y/N)
7. Immediate refactor ideas (≤ 2 lines).
```

4-3  Set **disposition** to one of:

* `KEEP`        – good as-is
* `RENAME`      – same code, better name/location
* `MERGE`       – duplicate with X, merge & delete this file
* `DELETE`      – unused scratch or generated
* `REWRITE`     – keeps feature but needs rewrite / lib extraction


--------------------------------------------------------------------
PHASE 5 – Architecture overlay             (~2 days)
--------------------------------------------------------------------

5-1  Export a pivot table:

* rows = component
* cols = disposition
* values = sum(loc)

This visualises where debt concentrates.

5-2  Draw a *component map* (whiteboard or draw.io) showing packages and
the direction of imports (`pip install grimp` can auto-generate).  Mark
modules flagged MERGE / REWRITE in red.

5-3  **Define/refresh Domain-Driven Design context**

```
▶  Create docs/architecture/ddd_contexts.md with one H2 per bounded context
▶  Map each *component* from the spreadsheet to one context
▶  If a file’s ideal_folder suggests moving across contexts, capture that in arch_notes.
```

--------------------------------------------------------------------

PHASE 6 – From audit to **actionable change** (continuous)
--------------------------------------------------------------------

This phase converts the static audit into a living refactor roadmap.

### 6-1  Derive a *risk ✕ reward* score

```python
import pandas as pd, numpy as np

df = pd.read_csv("audit_master.csv")

# Normalise metrics 0-1
df["loc_n"]   = (df.loc - df.loc.min())   / (df.loc.max()   - df.loc.min())
df["churn_n"] = (df.churn - df.churn.min()) / (df.churn.max() - df.churn.min())

# Risk = 0.7 × churn + 0.3 × size
df["risk"] = 0.7 * df.churn_n + 0.3 * df.loc_n

# Reward based on disposition
reward = {"KEEP":0, "RENAME":0.3, "DELETE":0.3, "MERGE":0.6, "REWRITE":1.0}
df["reward"] = df.disposition.map(reward).fillna(0)

df["priority"] = df.risk * df.reward
df.sort_values("priority", ascending=False).to_csv("audit_prioritised.csv", index=False)
```

Review `audit_prioritised.csv` – top rows are highest-value tech-debt.

### 6-2  Generate tracker issues automatically

Example using GitHub CLI (adjust for your tracker):

```bash
while IFS=, read -r path disposition priority arch impl ; do
  [[ "$disposition" == "KEEP" ]] && continue
  gh issue create \
     --title "TD:$disposition $path" \
     --label tech-debt,$(dirname "$path") \
     --body "Priority: $priority\n\nArch notes: $arch\nImpl notes: $impl"
done < <(tail -n +2 audit_prioritised.csv | head -50)
```

### 6-3  Batch *quick-wins* lane

Criteria: `loc < 80` **and** `disposition ∈ {RENAME, DELETE}`.

1. Group 10–20 such files.  
2. Apply mechanical changes (rename/move/delete).  
3. Run `pre-commit`, tests, open PR titled **“Tech-debt: quick-wins #1”**.

### 6-4  Large refactors – *strangler fig* approach

1. **Safety-net PR** – add integration tests covering current behaviour.
2. **Introduce new module** at `ideal_folder/ideal_filename` with clean
   API. Keep old code; route calls through façade.
3. **Migration PRs** – move callers incrementally.
4. **Removal PR** – delete old module once callers = 0.

Track progress by adding a `status` column (todo / in-progress / merged)
in `audit_master.csv`.

### 6-5  Guard-rails for every cleanup PR

```bash
pre-commit install        # lint & format
pdm run pytest -q         # full tests
scripts/run_mypy.sh       # if type-checking enabled
```

Add `ci/audit-sync.yml` that fails if a PR modifies a file but *does
not* update its row in `audit_master.csv`.

### 6-6  Quarterly re-baseline

Run **Phase 1** scripts again; store new columns `loc_qX`, `churn_qX`.
Plot trend lines to show debt burn-down.


--------------------------------------------------------------------
Appendix – Handy one-liners
--------------------------------------------------------------------

* List top-20 churned files:  
  `git log --name-only --pretty=format: | sort | uniq -c | sort -nr | head -20`

* Find duplicate class names:  
  `grep -R "^class " backend | cut -d: -f2 | sort | uniq -d`

* Module dependency graph (requires graphviz):

```bash
pip install pydeps
pydeps --max-bacon=2 --show-cycles backend/src/core/orchestrator.py
```

--------------------------------------------------------------------
✅ Deliverables after completing the playbook
--------------------------------------------------------------------

1. `audit_master.csv` (saved in `docs/audit/` or similar).  
2. Architecture map image (`docs/audit/component_map.svg`).  
3. Issue backlog in tracker, each linked back to row id in the sheet.  
4. “Debt dashboard” pivot table refreshed weekly.

> Run phases 1–3 quarterly; full playbook (1–6) every six months.


Here's the formatted markdown content ready for copy-pasting:

```markdown
## PHASE 6 – From audit to **actionable change** (continuous)

This phase converts the static audit into a living refactor roadmap.

### 6-1 Derive a *risk ✕ reward* score

```python
import pandas as pd, numpy as np

df = pd.read_csv("audit_master.csv")

# Normalise metrics 0-1
df["loc_n"]   = (df.loc - df.loc.min())   / (df.loc.max()   - df.loc.min())
df["churn_n"] = (df.churn - df.churn.min()) / (df.churn.max() - df.churn.min())

# Risk = 0.7 × churn + 0.3 × size
df["risk"] = 0.7 * df.churn_n + 0.3 * df.loc_n

# Reward based on disposition
reward = {"KEEP":0, "RENAME":0.3, "DELETE":0.3, "MERGE":0.6, "REWRITE":1.0}
df["reward"] = df.disposition.map(reward).fillna(0)

df["priority"] = df.risk * df.reward
df.sort_values("priority", ascending=False).to_csv("audit_prioritised.csv", index=False)
```

Review `audit_prioritised.csv` – top rows are highest-value tech-debt.

### 6-2 Generate tracker issues automatically

Example using GitHub CLI (adjust for your tracker):

```bash
while IFS=, read -r path disposition priority arch impl ; do
  [[ "$disposition" == "KEEP" ]] && continue
  gh issue create \
     --title "TD:$disposition $path" \
     --label tech-debt,$(dirname "$path") \
     --body "Priority: $priority\n\nArch notes: $arch\nImpl notes: $impl"
done < <(tail -n +2 audit_prioritised.csv | head -50)
```

### 6-3 Batch *quick-wins* lane

Criteria: `loc < 80` **and** `disposition ∈ {RENAME, DELETE}`.

1. Group 10–20 such files.
2. Apply mechanical changes (rename/move/delete).
3. Run `pre-commit`, tests, open PR titled **"Tech-debt: quick-wins #1"**.

### 6-4 Large refactors – *strangler fig* approach

1. **Safety-net PR** – add integration tests covering current behaviour.
2. **Introduce new module** at `ideal_folder/ideal_filename` with clean API. Keep old code; route calls through façade.
3. **Migration PRs** – move callers incrementally.
4. **Removal PR** – delete old module once callers = 0.

Track progress by adding a `status` column (todo / in-progress / merged) in `audit_master.csv`.

### 6-5 Guard-rails for every cleanup PR

```bash
pre-commit install        # lint & format
pdm run pytest -q         # full tests
scripts/run_mypy.sh       # if type-checking enabled
```

Add `ci/audit-sync.yml` that fails if a PR modifies a file but *does not* update its row in `audit_master.csv`.

### 6-6 Quarterly re-baseline

Run **Phase 1** scripts again; store new columns `loc_qX`, `churn_qX`.
Plot trend lines to show debt burn-down.
```