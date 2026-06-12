# LoRA Fine-Tune Plan — Local YouTube-Transcript Summarizer

**Goal:** replace the LLM-API summarization call in Merlin's YouTube plugin
(`merlin/knowledge_sources/plugins/youtube/summarizer.py`) with a small,
LoRA-fine-tuned model running locally on llama.cpp.

**v1 scope:** output languages **en / fr / de / es / it** (output language =
input language). All five are Latin-script European → same conventions (normal
`**bold**`, English headers fine), no special handling. **zh is much later** (it
needs script-specific convention work — bold on Chinese text, header language).

**Language-coverage strategy:** the corpus is ~entirely en/fr, so de/es/it have
almost no native training data. **v1.0 relies on cross-lingual transfer** — the
format is language-agnostic and the base model already knows de/es/it, so a model
trained on en/fr *format* should produce it in those languages too. The de/es/it
eval items (§7) test whether that holds. **Only if it doesn't** do you add real
de/es/it transcripts from YouTube-Commons (§3.3, v1.1).

Two summary modes (**short** / **detailed**), selected by **user toggle** (not
auto-routed).

**Author:** planning doc, updated 2026-06-11. Status: proposal.

---

## 0. TL;DR — the recommendation

1. **Don't train on the raw 787 pairs as-is.** They're noisy (3 teacher models,
   drifting prompts/formats). With a small dataset, target *consistency* beats
   volume. **Regenerate all targets** with one teacher (DeepSeek via OpenRouter)
   + one fixed prompt/schema, in **both length modes**. This distillation step is
   the single highest-leverage move.
2. **v1.0 = your existing 787 only; expansion is deferred.** The 787 (re-
   summarized, both modes ≈ ~1,500 rows) already teach the format in en/fr — your
   actual usage. Prove the whole pipeline on them first. The known risk is the
   *chain* (teacher → train → GGUF → serve → integrate), not data volume.
   **v1.1 (only if eval says so):** top up from
   **[YouTube-Commons](https://huggingface.co/datasets/PleIAs/YouTube-Commons)**
   (2M+ real YouTube ASR transcripts, multilingual, CC-BY), re-summarized by your
   teacher — for de/es/it anchoring and/or topic de-biasing, sized to whatever the
   v1.0 eval revealed (§3.3).
3. **Models — your inference ceiling ≠ your training ceiling.** On 16 GB you can
   *serve* 12B (160 tok/s) and even 27B 4-bit, but QLoRA *training* tops out at
   the **12B class**. With v1 scoped to en/fr, Qwen's Chinese edge is moot — pick
   on general en/fr quality + serving fit:
   - **Gemma 4 12B QAT** — primary. QAT-aware LoRA keeps int4 quality; you
     already serve it fast; strong en/fr.
   - **Gemma 4 E4B** — fast/cheap challenger for quick iteration; ship it if
     quality holds.
   - **Qwen 3.6 (≤12B dense)** — challenger on general quality (its zh strength
     only matters once de/zh are back in scope).
   - Qwen 3.6 **27B** is serve-only on this box (rent cloud if you must train it).
4. **QAT: yes, keep it.** Unsloth supports **QAT + LoRA** and ships Gemma 4 QAT
   checkpoints (E2B/E4B/12B/26B-A4B/31B). Do QAT-aware LoRA → GGUF int4 with
   near-bf16 quality, instead of a naive post-train quantize (which drops
   ~8–15 pts accuracy).
5. **MTP: leave out of training.** It's an inference-time speedup
   (self-speculative decoding — the source of your 160 tok/s). Fine-tune the
   next-token path normally; just **measure draft-acceptance/tok-s afterwards**.
   Only reach for **gated LoRA** if the fine-tune erodes the MTP speedup.
6. **Two modes baked in.** Condition on a `short` / `detailed` flag in the
   prompt; generate teacher targets for both modes per transcript. Keep that
   prompt byte-identical between train and serve.
7. **Env is low-risk** (CUDA 13.3, source-built llama.cpp). Still run a 2-min
   training smoke test before any real run (§2).

---

## 1. The dataset (from `export/DATASET.md`)

| Metric | Value |
|--------|-------|
| Total completed pairs | **787** (your own corpus) |
| Avg transcript | 3,611 words (~4,800–5,400 tokens) |
| Avg summary | 307 words (~430 tokens) |
| Max transcript | 48,983 words (~65K tokens — rare outlier) |
| Teacher models | gpt-4.1 ×715, deepseek-v4-flash ×20, unknown ×52 |
| Lang (`detected_language`) | unknown ×691, en ×77, fr ×19 |

Two facts drive the plan: **787 is small** (fine for LoRA — quality/consistency
of targets matters far more than volume), and **the targets are inconsistent**
(three teachers + drifting prompt = the model is asked to learn a *distribution
of formats* rather than one). Fix consistency first; add diversity second.

> `detected_language` is mostly `unknown` (a metadata gap), not "mostly
> non-English." Detect language at clean-up time, don't trust this column.

---

## 2. Hardware & environment (low-risk, but gate it)

Box: **RTX 5070 Ti (16 GB, Blackwell `sm_120`), R7 5800X, 64 GB DDR4, CachyOS,
CUDA 13.3, llama.cpp built from source.** Measured serving: Gemma 4 12B QAT+MTP
4-bit ≈ **160 tok/s, ~3000 pp, 260K ctx**; Qwen 3.6 27B 4-bit ≈ **40 tok/s,
~1200 pp, 60K ctx**.

- **Serving** is clearly not the constraint — you run 12B–27B comfortably.
- **Training** is the constraint. QLoRA on 16 GB is comfortable up to ~12B at a
  reasonable context; 27B QLoRA on 16 GB is impractical (heavy offload, very
  slow) — treat 27B as serve-only here.
- **PyTorch needs `sm_120` kernels**, independent of system CUDA 13.3 (torch
  bundles its own CUDA runtime). Use Unsloth's Blackwell image or cu12.8+ wheels
  and confirm `torch.cuda.get_device_capability() == (12, 0)`.
- Keep the training stack (Unsloth, torch) in **its own venv**, separate from
  Merlin's `uv` env. Merlin only ever needs the *inference* client (a URL to
  llama-server), never the trainer.

**Gate:** a 2-minute smoke test — load a tiny model in Unsloth, run one training
step, print device capability `(12,0)` — before any real run.

Sources: [Unsloth Blackwell docs](https://docs.unsloth.ai/basics/fine-tuning-llms-with-blackwell-rtx-50-series-and-unsloth),
[Unsloth requirements](https://unsloth.ai/docs/get-started/fine-tuning-for-beginners/unsloth-requirements),
[llama-cpp-python Blackwell build](https://github.com/abetlen/llama-cpp-python/issues/2028).

---

## 3. Data pipeline — the part that actually matters

### 3.1 The schema already exists — finalize it

The output contract is drafted in
`merlin/knowledge_sources/plugins/youtube/prompts/summary_short.md` and
`summary_details.md` (markdown `## Overview` / `## Key Points` [/ `## Analysis`
/ `## Takeaways`], body in `{lang}`, headers in English, insight-first bullets,
en+fr few-shots). These are a clear upgrade over the inline short/medium/long
templates still in `summarizer.py` — standardize on them, drop `medium`. Before
they become training targets, finalize four things:

- **Few-shots are teacher-only.** The `## Few-shot examples` blocks are the right
  scaffold for the DeepSeek teacher (§3.2) to pin format. But fine-tuning bakes
  the format into the weights, so the **training input and the serve-time prompt
  are the instruction block only (system + user template), with the few-shots
  stripped.** The invariant is: the *instruction* portion is byte-identical
  train↔serve; the examples live only in the data-gen script. (Otherwise you pay
  ~2K tokens every inference and waste part of the fine-tune.)
- **Few-shots: en+fr is enough.** The drafts' one en + one fr example demonstrate
  the format and the "body in `{lang}`" rule; the teacher (DeepSeek) follows the
  language instruction without a per-language example. de/es/it coverage comes
  from data (cross-lingual transfer + optional anchoring, see scope note), not
  from more few-shots. Optionally add one de or es example if eval shows format
  drift in those languages.
- **Timestamps — DECIDED: killed.** The old `Main Topics` + `[timestamp]` section
  is gone (the drafts already dropped it; raw subtitles carry no time markers, so
  those timestamps were hallucinated). Action items: remove
  `extract_topics_and_timestamps()` from `summarizer.py`, simplify the summarize
  return to just the summary string, stop persisting `topics`/`timestamps` in the
  ingest path, and audit/clean UI references (item card, library detail). Leave
  the DB columns nullable for now; drop them in a later migration if desired.
- **`## Analysis` (detailed mode) is the risky/expensive section.** It licenses
  the model to "go beyond the video," which fights faithfulness and is where a
  small model hallucinates — and where **12B visibly beats 4B/E4B.** Eval (§7)
  must score it on insight/non-triviality, not transcript-faithfulness.

Mode is a **user toggle** (`short`/`detailed`), passed explicitly in the prompt —
not auto-routed. For training, generate both-mode targets per transcript so the
model honors the flag either way.

### 3.2 Regenerate clean targets (distillation)

Keep the **transcripts** (raw subtitle text is a fine input); discard the
existing summaries as *targets*. Re-summarize every transcript with **one
teacher, one prompt, both modes**:

- **Teacher:** DeepSeek ("v4 pro" tier) via OpenRouter — cheap big-batch, strong
  enough to be a clean ceiling for a 12B student. Spot-check **fr** output
  quality (it's a first-class v1 language, not an afterthought).
- New `scripts/regenerate_summaries.py` (sibling to `export_training_data.py`):
  read transcripts → call OpenRouter with concurrency + retry → write
  `export/clean_pairs.jsonl` with a `mode` field per record. Cache by
  `(video_id, mode)` so re-runs are cheap. ~787 × 2 modes × ~5K input tokens
  ≈ <10M input tokens — a few dollars.

### 3.3 Expansion: in-domain public transcripts (v1.1 — deferred)

**Skip this for v1.0.** Run the pipeline on your 787 first; add this only if the
v1.0 eval shows a concrete gap — weak de/es/it transfer (§7) or topic brittleness.
When you do, it has three jobs: (a) increase size, (b) cover content *kinds* your
library underrepresents, (c) supply real de/es/it examples. All from **one source,
re-summarized by your teacher** — never the source's native summaries (format
drift). Targets always come from the teacher; the public data only supplies
*input transcripts*.

**Primary source — [PleIAs/YouTube-Commons](https://huggingface.co/datasets/PleIAs/YouTube-Commons).**
The best fit by far:
- 2M+ videos / 22.7M transcripts / 721k channels — unlimited diversity to sample.
- Multilingual incl. **en/fr/de/es/it** — covers topic diversity *and* de/es/it
  anchoring from one place.
- **Real YouTube ASR transcripts** → same register as Merlin's own data (spoken,
  imperfect punctuation). That's a feature: it matches deployment, unlike written
  news.
- **CC-BY** (attribution; low concern for a personal tool, matters only if you
  publish the model). Ships provenance (title/channel/date); no summaries.
- Caveats: non-English rows include **auto-translations** — for de/es/it
  anchoring prefer **original-language** rows (authentic register); 71% is
  English so **filter by language** to balance; big sharded dataset, expect to
  stream/filter, not load wholesale.

**Optional — [HowTo100M](https://www.di.ens.fr/willow/research/howto100m/).**
Only if you want more **English instructional** content (cooking/crafting/etc.).
Drawbacks: English-only, clip-fragmented ASR (reconstruct per-video), older.
Lower ROI than YouTube-Commons.

**Skip / verify first — AIAAIC "YouTube subtitles dataset".** Hosted in an AI
*incidents* repository → likely flagged for consent/scraping/ethics issues, not a
clean corpus. Check provenance + license before any use; YouTube-Commons covers
the same need cleanly.

**Fallback (clean written text, if ever needed):** WikiLingua (en/fr/de/es/it
how-to), MLSUM (de/es/fr), XL-Sum — but these are *written* register; cap their
share so the model doesn't drift toward news prose.

**Don't engineer topic diversity — you don't need it.** This is a *format/style*
fine-tune, not a knowledge task: the mapping transcript→structured-summary is
largely topic-independent (the base model already understands any topic; you're
only biasing output shape), and a modest-rank LoRA can't memorize topic-specific
behavior anyway. With 721k channels in the source, **random sampling already
spans hundreds of topics** — no classifier, clustering, or stratification needed.
Size the supplement for **language coverage + de-biasing**, not topic coverage
(topics come free).

**Sampling recipe** (three filters; none is "topic"):
1. **Language** — filter `original_language ∈ {en,fr,de,es,it}` (skip
   auto-translated rows). This is the real reason to sample — de/es/it anchors.
2. **Per-channel cap** (~2–3 videos/channel) — the highest-value, near-free
   diversity lever; stops one creator/niche from dominating.
3. **Length band** — ~800–8,000 words; drop tiny clips and giant streams.

**How much:** ~50–150 per de/es/it; en/fr optional (you already have 787 that
teach the format) → **total supplement ~500–1,500**. Past ~2k is near-zero
marginal gain for a format task. Re-summarize both modes; log per-source /
per-language / per-mode counts.

### 3.4 Clean, format, split

- **Long tail:** transcripts up to ~49K words. Truncate to the training context
  window or exclude from v1 (<5%); log what you drop — no silent capping.
- **Dedup** near-identical transcripts (channel re-uploads).
- **Sanity filters:** drop pairs where summary ≥ transcript length, empty, or
  contains teacher artifacts ("As an AI…").
- **Chat template:** keep the ChatML `messages` shape, but apply **each model's
  own chat template** at train time (Gemma 4 and Qwen 3.6 differ — let the
  tokenizer handle it).
- **Mask the prompt — train on responses only.** Input is ~10× the output;
  Unsloth's `train_on_responses_only` ensures loss is on summary tokens, so the
  model doesn't just learn to echo transcripts. Critical.
- **Split:** ~90/10, stratified by **(language, mode, length bucket)**. Freeze an
  eval set spanning both modes — heavy on en/fr, plus a **handful of de/es/it
  items** (even just teacher-summarized public transcripts) to verify
  cross-lingual transfer.

---

## 4. Model shortlist

Constraint: QLoRA *training* on 16 GB → 12B-class ceiling. Serving is not a
constraint.

| Model | Role | Why |
|-------|------|-----|
| **Gemma 4 12B (QAT)** | **Primary** | QAT-aware LoRA keeps int4 quality; you already serve it at ~160 tok/s; strong en/fr; Apache-2.0. Trainable on 16 GB via QLoRA. |
| **Gemma 4 E4B (QAT)** | Fast challenger | Elastic/efficient; fast to train and serve. Ship it if quality holds — cheapest iteration loop. |
| **Qwen 3.6 (≤12B dense)** | Challenger | General-quality challenger; its zh strength only pays off once de/zh return to scope. |
| Gemma 4 E2B / Llama-class 3–4B | Floor baseline | Measures whether the bigger models earn their cost. |
| Qwen 3.6 27B | **Serve-only** | Too big to QLoRA on 16 GB; rent a cloud GPU if you genuinely need it as the student. |

**Plan:** fine-tune **Gemma 4 12B** (and try **E4B** first — if it clears the
bar, it's the best quality/speed/iteration trade) on the clean en/fr dataset.
Keep a Qwen 3.6 ≤12B run as a challenger, but Gemma is favored for v1.

Sources: [Gemma 4 QAT (Unsloth)](https://unsloth.ai/docs/models/gemma-4/qat),
[Gemma 4 fine-tuning guide](https://unsloth.ai/docs/models/gemma-4/train),
[Gemma 4 QAT (Google)](https://blog.google/innovation-and-ai/technology/developers-tools/quantization-aware-training-gemma-4/),
[Qwen 3.6 vs Gemma 4 multilingual](https://medium.com/data-science-in-your-pocket/gemma-4-12b-vs-qwen-3-6-27b-which-open-model-wins-in-coding-translation-and-vision-570c710b1045).

---

## 5. QAT & MTP — how they fit

### QAT (quantization-aware training) — use it
- Unsloth supports **QAT + LoRA together** (schemes incl. int4, int8-int4,
  fp8-int4) and ships Gemma 4 QAT checkpoints (E2B/E4B/12B/26B-A4B/31B).
- Naive post-training quant of a QAT checkpoint to `Q4_0` can lose a lot
  (one cited case: 70.2% → recovered to 85.6% with Unsloth's dynamic GGUF).
  So: **start from the QAT checkpoint, do QAT-aware LoRA, export with Unsloth's
  dynamic GGUF** to keep near-bf16 quality at int4.
- Net effect: smaller VRAM during training *and* a 4-bit serve model that
  doesn't visibly degrade vs bf16.

Source: [Unsloth QAT](https://unsloth.ai/docs/blog/quantization-aware-training-qat).

### MTP (multi-token prediction) — inference-time only
- MTP = self-speculative decoding; it's what gives your 160 tok/s. It is **not**
  something you train for a summarization adapter.
- Fine-tune the standard next-token path. Risk: vanilla LoRA can lower the MTP
  draft head's **acceptance rate**, shrinking the speedup (main-path quality is
  unaffected).
- **Mitigation only if needed:** "gated LoRA" applies separate paths for NTP vs
  MTP tokens and is reported to avoid that degradation. v1: train normally, then
  **measure tok-s + acceptance after the fine-tune**; adopt gated LoRA only if
  the speedup actually dropped.

Source: [MTP / gated LoRA paper](https://arxiv.org/abs/2507.11851).

---

## 6. Training (Unsloth / QAT-LoRA)

Starting hyperparameters — tune from here:

| Setting | Value | Note |
|---------|-------|------|
| Method | **QAT-LoRA** (int4) | keeps int4 serve quality; cuts train VRAM |
| `max_seq_length` | **8192** | covers avg + headroom; long tail truncated (§3.4) |
| LoRA rank `r` | 16 (try 32) | plenty for a style/format/length-control task |
| `lora_alpha` | 32 (= 2×r) | |
| Target modules | attention + MLP proj | Unsloth default |
| `train_on_responses_only` | **True** | loss on summary tokens only — critical |
| Epochs | 2–3 | small data overfits fast; early-stop on eval loss |
| LR | 2e-4 | cosine, ~5% warmup |
| Effective batch | 8–16 | grad accumulation; real batch maybe 1–2 at 8K/12B |
| Precision | bf16 compute | Blackwell handles bf16 well |

One Unsloth script parameterized by base model so all candidates run from the
same code. Mix your 787 + any diversity supplement (§3.3) into one shuffled set;
keep en/fr balance reasonable. Log train + eval loss per language.

Sources: [Gemma 4 fine-tuning guide](https://unsloth.ai/docs/models/gemma-4/train),
[Unsloth benchmarks](https://unsloth.ai/docs/basics/unsloth-benchmarks).

---

## 7. Evaluation — per language, per mode

Summarization has no single metric; use a small battery on the frozen eval set,
**broken out by language (en/fr core; de/es/it transfer check) and mode
(short/detailed)**:

1. **LLM-as-judge (primary).** A strong model (ideally a *different* family than
   the teacher, to avoid self-bias) scores 1–5 on faithfulness, coverage,
   format-adherence, conciseness, **and answers-in-correct-language**. Compare
   fine-tuned vs base vs teacher on identical items.
2. **Format + language compliance (automatic).** Parse-check required sections
   per mode; detect output language == input language. A core reason to
   fine-tune is reliable structure + language — measure it directly.
3. **ROUGE/length sanity** as a weak secondary signal.
4. **Eyeball outputs per language.** Catches degeneration metrics miss — watch
   **fr** as closely as en, and sanity-check the de/es/it samples for correct
   language + format (the transfer check).

**Ship criterion:** fine-tuned model reaches ≥ ~90% of teacher's judge score
with ≥ 95% format+language compliance **in en and fr**, with de/es/it producing
correct language + format on the transfer check, at acceptable local latency. If
de/es/it transfer is weak → add anchoring data (§3.3). If quality lags broadly →
try Gemma 4 E4B → 12B (12B is primary) or the Qwen 3.6 challenger, and add data
before adding epochs.

---

## 8. Quantize & deploy on llama.cpp

1. **Merge QAT-LoRA → base** (Unsloth merged save).
2. **Export GGUF with Unsloth's dynamic method** (preserves QAT int4 quality)
   rather than a plain convert+quantize.
3. **Quant target:** `Q4_0`/Q4_K_M-class from the QAT path (that's the point of
   QAT). A 12B int4 ≈ 7–8 GB — fits with huge context headroom on 16 GB, and you
   already measured 160 tok/s with MTP.
4. **Serve** with `llama-server` (OpenAI-compatible `/v1/chat/completions`),
   built for `sm_120`, `-ngl 99`, flash attention on, MTP/speculation enabled.
   Watch **prompt-processing** throughput (the ~5K-token transcript dominates
   latency, not generation).

Sources: [llama.cpp CUDA performance](https://github.com/ggml-org/llama.cpp/discussions/15013),
[unsloth/gemma-4-12B-it-qat-GGUF](https://huggingface.co/unsloth/gemma-4-12B-it-qat-GGUF).

---

## 9. Integrate into Merlin

`merlin/config.py` already has an `LLM_PROVIDER` switch and the summarizer is
isolated — this stays clean.

- Add `LLM_PROVIDER=llamacpp` + `LLAMACPP_BASE_URL` to `Settings`;
  `settings.llm` builds a `ChatOpenAI` pointed at `http://localhost:8080/v1`
  (llama-server is OpenAI-compatible — existing LangChain plumbing just
  repoints).
- `plugins/youtube/summarizer.py` keeps calling the abstract LLM — **no change**
  if it uses `settings.llm`. Make the §3.1 prompt (with the `short`/`detailed`
  mode line and the language rule) the summarizer's prompt so train-time and
  serve-time prompts are identical.
- Docker: run `llama-server` as a **sidecar service** (current setup is
  single-service Streamlit) with the GGUF mounted as a volume, or run it on the
  host and point Merlin at it. GPU-in-Docker needs the NVIDIA container toolkit.
- **Keep OpenRouter/Azure as fallback** for transcripts over the local context
  window (long tail) or when the server is down.

This preserves the one rule: `merlin/` imports no Streamlit; the model is just
another backend behind `settings.llm`.

---

## 10. Phased checklist

- [ ] **Phase 0 — Env (½ day).** cu12.8+ torch with `sm_120`, Unsloth, one-step
      smoke test passes; llama-server built for `sm_120` (CUDA 13.3 — easy).
- [ ] **Phase 1 — Schema + clean data (½–1 day).** Finalize the short/detailed
      prompts. `scripts/regenerate_summaries.py`: re-summarize **your 787**
      transcripts × 2 modes via DeepSeek/OpenRouter. Clean, dedup, mask,
      stratified 90/10 split + frozen eval (slip in a few de/es/it items for the
      transfer check). *No YouTube-Commons in v1.0 — that's the §3.3 v1.1 top-up.*
- [ ] **Phase 2 — Train (½ day).** QAT-LoRA Gemma 4 (E4B first, then 12B), Qwen
      3.6 ≤12B as challenger, from one script. Log per-language loss.
- [ ] **Phase 3 — Eval (½ day).** Judge battery per language/mode vs base +
      teacher. Pick winner; check en/fr compliance + the de/es/it transfer check;
      add more anchoring data if a language lags.
- [ ] **Phase 4 — Deploy.** Merge → dynamic GGUF int4 → llama-server; verify
      tok-s + MTP acceptance held.
- [ ] **Phase 5 — Integrate.** `llamacpp` provider; align summarizer prompt; A/B
      local vs API on fresh ingests; keep API fallback for the long tail.

---

## 11. Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Public data drags model toward news prose | Re-summarize through your teacher; prefer transcript-like sources; cap news share |
| fr quality lags en | fr is first-class v1; spot-check teacher fr; keep en/fr balanced; eval fr separately |
| de/es/it transfer weak (no native train data) | Validate on the transfer eval set; add ~30–60/lang anchoring data (§3.3) only if needed |
| zh/other input shows up (rare) | Out of scope for v1 — fall back to API, or default output to en; revisit zh later (needs convention work) |
| 27B temptation | It's serve-only on 16 GB; train ≤12B locally or rent cloud for 27B |
| Naive quant kills QAT benefit | Start from QAT checkpoint; export via Unsloth dynamic GGUF |
| Fine-tune erodes MTP speedup | Measure acceptance after; adopt gated LoRA only if needed |
| Prompt skew (train vs serve) | One prompt (mode + language rule) shared by teacher script and summarizer |
| Overfit on small data | 2–3 epochs, early-stop on eval loss, modest rank |
| Self-judge bias | Judge with a different family than the teacher |

---

## 12. Open decisions for you

1. **Finalize the short/detailed prompts** — confirm section/bullet counts.
2. **Teacher model id** on OpenRouter (the DeepSeek "v4 pro" tier).
3. **Primary student to ship** — default Gemma 4 12B; try E4B first for the fast
   loop; keep Qwen 3.6 as challenger.
4. *(v1.1, deferred)* **YouTube-Commons top-up** — size + per-language balance,
   decided only if the v1.0 eval shows a gap (§3.3).

**Resolved:** v1 output langs = **en/fr/de/es/it** (en/fr from your data, de/es/it
via cross-lingual transfer + optional anchoring; **zh much later**); mode = user
toggle; **timestamps killed** (§3.1 lists the code cleanup).
