# Demo runbook — retrieval transparency

**Audience:** the engineering team. **Length:** ~10 minutes. **Date:** 2026-08-10.

The story in one sentence: *our similarity score cannot tell an on-topic question
from an off-topic one, we already fixed the ranking to not depend on it, and as
of today you can see that happening.*

> **On the numbers.** The original measurements (2026-07-28) were 0.501 on-topic
> vs 0.514 off-topic. Re-measured live on 2026-08-10 the pair is 0.49 vs 0.51 —
> the corpus has grown since, so exact values drift. The *ordering* is what
> matters and it has not changed: off-topic still outscores on-topic. Quote what
> is on the screen, not the older pair, if someone asks.

---

## Before you start

```powershell
just dev
```

Then open <http://localhost:4321> and pick **Semua produk** at the scope gate.

**Quota:** the Gemini key is free tier — 20 `generateContent` requests per day
per model, and one agent turn can spend 5+. Three demo questions is comfortably
inside that, but a rehearsal plus the real thing may not be.

To rehearse without spending any quota, start with fake mode on:

```powershell
$env:LLM_FAKE_MODE='true'; just dev
```

The evidence panel is built in the `tools` node, **before** the model is called
at all, so every number below is identical either way. What changes is only the
prose above the panel. If the quota runs out mid-demo the app degrades to the
same offline answer automatically — that is worth pointing out rather than
apologising for.

---

## The three questions

### 1. "gimana cara menjalankan proyek ini di lokal?"

The control. Expect **Cocok banget** (high confidence) and a panel where the
winning passage is the one whose *heading* matches:

```
TEP CMS … > Tech Stack & Cara Menjalankan > Menjalankan di lokal
0.49 · 6 kata sama · DIPAKAI
```

Verified live on 2026-08-10: **Cocok banget**, `3 dari 8 bagian dipakai`.

**Point out:** the top score here is **0.49**. Remember that number.

A heading hit counts double in the overlap score, which is why the section that
answers beats the table of contents that merely lists the phrase in a cell —
those two tied on body words against the real index.

### 2. "resep rendang padang yang enak untuk lebaran" ← the moment

Expect **Nggak ada yang cocok** (confidence `none`), an explanatory note, and
every passage struck through as **Dilewati**. Verified live against the real
index today:

```
Engauge … > 2. Hasil yang Diharapkan > B. User Sudah Pernah Aktivasi
0.51 · nggak ada kata yang sama · DILEWATI

Klob Mobile > 5. Klob Meter > 5d. Hasil Tes (Detail Hasil)
0.51 · nggak ada kata yang sama · DILEWATI
```

Verified live on 2026-08-10: **Nggak ada yang cocok**, `0 dari 8 bagian dipakai`.

**Say this out loud:** a recipe question scores **0.51**. The real documentation
question in step 1 scored **0.49**. The off-topic question wins.

That is the whole argument in two screens. There is no threshold you can put
between 0.49 and 0.514 that keeps the first and drops the second — and the gap
goes the wrong way, so raising the bar would reject the *right* answer first.

The cause: the index is built with `BAAI/bge-small-en-v1.5` (`indexing.py`)
while `docs/knowledge-base/` is almost entirely Indonesian. An English-only
model reads all Indonesian text as roughly equidistant, so the scores cluster
and the ordering inside that cluster is close to noise.

What actually separates them is the **keyword overlap** column: 8 vs 0. That is
what `agent/relevance.py` gates on, with the score demoted to a tiebreak plus a
floor for outright garbage.

### 3. "teknologi apa yang dipakai di TEP CMS?"

The detail that makes the gate work. Expect a confident answer citing the TEP
CMS tech stack section.

**Point out:** the content-word floor is **3 characters, not 4**. With a
four-character floor, `tep` and `cms` — the only two words that identify the
product — get thrown away before matching, and this question returns nothing
despite the index holding a 0.662 match for it. That was the highest score of
any question measured.

Matching is *prefix-of-token*, not substring-of-text, which is what keeps three
letters safe: as a bare substring `tep` also hits "step" and `api` hits
"aplikasi".

---

## What to show in the code (2 minutes)

- `apps/backend/src/agent/relevance.py` — one module, pure functions, no model
  and no I/O. Both the offline answer path and the evidence panel read from it,
  so the panel can never disagree with the answer about what counted.
- `apps/backend/src/agent/test_relevance.py` — `just test-be`. Every threshold
  in that file has a test that encodes the measurement behind it, so changing a
  number fails loudly instead of silently degrading retrieval.
- `evals/cases/relevance/off-topic-outscores-on-topic.yaml` — the rendang case,
  now a regression test.

---

## Closing slide: what this does NOT fix

Be explicit about the scope, because the obvious follow-up question is "so is
retrieval fixed?" — and the answer is no.

- **This release is observation only.** The ranking is displayed; it does not
  change which chunks the model receives. The model still sees the raw top-k.
  Feeding the ranking back into the model's input is a genuine behaviour change
  and needs its own eval cases before it ships.
- **The root cause is still there.** The real fix is a multilingual embedding
  model — `bge-m3` or `multilingual-e5` — in `indexing.py`. That is ADR-sized:
  it changes vector dimensions and requires a full `just reindex`. Proposing it
  is the natural next step, and this demo is the evidence for why it is worth
  doing.
- **Synonyms still miss.** A question phrased entirely in words the docs do not
  use ("cara run aplikasi" against docs that say "menjalankan") fails the
  overlap gate and gets the honest "nothing found" note. Accepted knowingly: a
  confidently wrong answer is the more expensive failure.
