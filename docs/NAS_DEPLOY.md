# NAS Deployment — Target Hardware Reference

The production deploy runs in **Docker on a home NAS** (dev also happens against
the same box). This is the authoritative spec of that target, for sizing any
CPU/RAM-bound work (vector search, self-hosted models, transcription, etc.).

## Hardware — UGREEN DXP2800

| Component | Spec |
|-----------|------|
| **CPU** | Intel **N100** — 4 cores / 4 threads (no HT), Gracemont E-cores only |
| CPU clocks | base low (6 W class), turbo up to 3.4 GHz, min 700 MHz; sustains well below turbo under load |
| **SIMD** | AVX, **AVX2**, FMA, F16C, AVX-VNNI, VAES — **no AVX-512** |
| Other ISA | AES-NI, SHA-NI, BMI1/2, RDSEED |
| Cache | L1d 128 KiB (32 KiB/core), L1i 256 KiB, **L2 2 MiB shared**, **L3 6 MiB shared** |
| **RAM** | **8 GB DDR5** (single NUMA node) |
| GPU | integrated UHD only — **not usable for ML inference** in practice |
| Virtualization | VT-x (the app runs in Docker, not a VM) |

## Memory budget (the real constraint)

8 GB total, shared with the NAS OS + other services + Docker overhead. Observed
container footprint at idle:

```
CONTAINER       MEM USAGE / LIMIT     MEM %
merlin-api-1    257.2 MiB / 7.507 GiB  3.35%
```

So the API itself is light (~260 MB). The container sees a ~7.5 GiB limit, but
**do not plan to the limit** — the host OS and any other NAS apps live in the
same 8 GB. Treat **~1–1.5 GB of additional resident memory** as the safe ceiling
for new in-process work (cached vector matrix, self-hosted models, etc.).

## Implications for compute-bound features

- **Vector search (numpy + float32 BLOB).** Comfortable. GEMV over the corpus is
  memory-bandwidth bound, not compute bound, so the lack of AVX-512 is
  irrelevant — AVX2 already saturates loads. A cached `(N×1024)` float32 matrix
  is 4 MB @ 1k items, 40 MB @ 10k — trivial against the RAM budget. See
  `VECTOR_SEARCH.md`. **Pin `OMP_NUM_THREADS=1`** so BLAS doesn't oversubscribe
  the 4 cores shared with uvicorn + the 3 ingest workers.
- **Self-hosting embeddings / reranking.** Feasible *only with small ONNX-Runtime
  INT8 models*, not PyTorch + large checkpoints (those blow the 8 GB budget).
  Recommended: self-host **`multilingual-e5-small`** as an
  `EMBEDDING_PROVIDER=local` embedder (~240 MB, 100+ langs, 384-d, ~5–15 ms/query,
  drop-in `Embedder` Protocol impl — needs the E5 `query:`/`passage:` prefixes)
  and **keep reranking on Jina** — the strong multilingual cross-encoder
  (`bge-reranker-v2-m3`) runs 2–4 s for ~10 docs on this CPU, and the fast
  rerankers are English-only. Full decision + the multilingual/lightweight/CPU
  trade-off + free-tier/key-rotation math in `VECTOR_SEARCH.md` → "Running it on
  the NAS".
- **No GPU.** Anything that assumes CUDA (heavy local LLM inference, large
  rerankers) is out. Keep the LLM and, by default, embeddings/rerank on hosted
  APIs (Azure/OpenRouter/Jina).
- **Thread contention.** 4 cores, no hyperthreading, shared across uvicorn, the
  3-worker ingest `ThreadPoolExecutor`, ffmpeg/transcription, and any model
  inference. CPU-bound additions should cap their own thread counts.
