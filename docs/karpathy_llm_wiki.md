Karpathy’s “LLM Wiki” concept, which gained massive traction in April 2026, represents a fundamental paradigm shift in how we handle personal knowledge management. As an ML engineer, you’re likely familiar with the limitations of standard Retrieval-Augmented Generation (RAG). Standard RAG is stateless: it retrieves chunks, answers your query, and forgets. Every session starts from scratch. 

Karpathy flipped this by treating **Obsidian as the IDE, the LLM (Claude Code) as the programmer, and the knowledge base as the codebase.** Instead of retrieving raw data on the fly, the agent actively compiles, cross-references, and maintains a structured network of markdown files. Your knowledge *compounds* over time.

Here is a deep analysis of the architecture, community feedback, and a step-by-step guide to implementing it yourself.

---

### 1. The Core Architecture

To understand the system, you have to separate the viewer from the engine:
* **The Viewer (Obsidian):** You do not write notes in Obsidian. You use it strictly as a front-end to navigate the local markdown files, read the synthesized pages, and visualize the `[[wikilinks]]` via the graph view. 
* **The Engine (Claude Code):** This is the agentic worker. It reads raw files, extracts entities, writes Wikipedia-style concept pages, and autonomously links them together. 
* **The Schema (`CLAUDE.md`):** The absolute most critical part of the setup. This file lives in the root directory and acts as the system prompt/rulebook for Claude Code, dictating the ontology of your wiki (e.g., how to format pages, when to create new entity pages, and how to log updates).

### 2. Community Feedback & Key Insights

Since the pattern dropped, the developer community has heavily stress-tested it. Here is the consensus and the best tips that have emerged:

* **Massive Token Savings:** A major revelation from the community (heavily discussed on places like r/ClaudeCode) is that this setup drastically reduces context token usage. Instead of feeding 20 raw research papers into context for every query, Claude reads the *synthesized* wiki pages. Users are reporting up to an 84% reduction in session startup tokens.
* **The "Linting" Trick:** Because the wiki is essentially a codebase, you can run QA on it. The community recommends periodically telling Claude Code to **"lint the wiki."** The agent will autonomously scan your repository to flag orphaned pages, dead links, stale claims, and—most impressively—contradictions between different research papers.
* **Topic Segmentation:** Don't put your entire life into one wiki. The community found that a single, monolithic wiki quickly turns into a hallucinatory hairball. Build topic-specific wikis (e.g., one for `RAG_Architecture`, one for `Diffusion_Models`).
* **Plugin Ecosystem:** Developers have already built Claude Code plugins like `claude-obsidian` to automate the taxonomy and initialization, which you can pull from the Claude plugin marketplace to skip boilerplate setup. 

---

### 3. How to Implement It Yourself (Step-by-Step)

You can build the vanilla Karpathy setup in about 15 minutes using just your terminal, Claude Code, and Obsidian. 

**Step 1: Set Up the File Structure**
Create a new directory for your project. The separation of `raw` and `wiki` is non-negotiable. The AI reads from `raw` but never edits it; it writes exclusively to `wiki`.
```bash
mkdir ml-wiki && cd ml-wiki
mkdir raw
mkdir wiki
```

**Step 2: Create the `CLAUDE.md` Schema**
Create a `CLAUDE.md` file in the root of `ml-wiki`. This tells Claude exactly how to behave. You can tailor this, but a strong starting prompt looks like this:
> "You are an autonomous knowledge base maintainer. Your job is to read sources from the `raw/` directory and compile them into interlinked markdown files in the `wiki/` directory. 
> 1. When I ask you to 'ingest' a file, extract the core concepts, frameworks, and entities.
> 2. Create individual `.md` pages for new concepts in `wiki/`.
> 3. Update existing pages if the new source adds relevant context or contradicts previous data. 
> 4. Liberally use Obsidian-style `[[wikilinks]]` to connect concepts. 
> 5. Log every action with a timestamp in `wiki/log.md`."

**Step 3: Connect Obsidian**
Download Obsidian and click **"Open folder as vault."** Select your `ml-wiki` folder. You won't see much yet, but this primes your graph view and markdown viewer.

**Step 4: The Ingestion Loop**
Drop a source file (a PDF of a paper, a markdown file from the Obsidian Web Clipper, or a transcript) into the `raw/` folder. 

Open your terminal in the root directory, authenticate Claude Code (`claude`), and run your first command:
```bash
claude
> Ingest raw/attention-is-all-you-need.pdf
```
Watch your Obsidian vault. You will see Claude dynamically generate the `log.md`, extract concepts (e.g., `Transformer.md`, `Self-Attention.md`), and link them together.

**Step 5: Compound and Query**
Add a second paper (e.g., a recent paper on Long-Context LLMs) to `raw/` and ingest it. Claude won't overwrite your `Self-Attention.md` page; it will update it with the new paper's findings, linking the evolution of the concept. 

Once your wiki is populated, you stop asking Claude general questions. Instead, you ask: *"Based on my wiki, summarize the evolution of context windows."* Claude will traverse your local graph, citing specific `[[concept]]` pages, giving you a deeply grounded, hallucination-free response based entirely on your curated dataset. When it gives you a great synthesis, just tell it: *"Save that answer as a new concept page."*



Here are the foundational prompts shared by Andrej Karpathy in his original April 2026 GitHub Gist, alongside the optimized prompts the developer community has built on top of it. 

Because Claude Code automatically reads a `CLAUDE.md` file in your root directory before starting any session, **the system prompt is the architecture.** Here is the exact framework you need to implement.

### 1. The Core Engine: Karpathy's `CLAUDE.md` Schema
This is the foundational prompt that sits in your root directory. It tells the agent its identity, establishes the strict boundary between raw data and synthesized knowledge, and enforces Obsidian's formatting rules.

Copy and paste this into a `CLAUDE.md` file in your project root:

> **Identity & Purpose**
> You are an autonomous knowledge base maintainer. Your objective is to build and maintain an "LLM Wiki"—a compounding, interconnected knowledge graph based entirely on the sources provided to you.
> 
> **Directory Rules**
> - `raw/`: This folder contains immutable source documents (PDFs, transcripts, markdown web clips). You may **READ ONLY** from this directory. Never modify or delete these files.
> - `wiki/`: This is your domain. You have full read/write access to this directory. You will create, update, and maintain structured markdown files here.
> 
> **Behavioral Directives**
> 1. **Entity Extraction:** When processing a new source, extract core concepts, frameworks, and entities. Create a separate `.md` page for every distinct concept in the `wiki/` directory.
> 2. **Cross-Referencing:** You must aggressively interlink concepts using Obsidian-style double brackets (e.g., `[[Self-Attention]]`). 
> 3. **Updating Existing Pages:** If a new source mentions a concept that already has a page, do not overwrite the page. Instead, append the new information, synthesizing how the new source agrees, expands, or contradicts the existing knowledge.
> 4. **Tracking:** After every ingestion, update `wiki/index.md` with new pages and log your actions with a timestamp in `wiki/log.md`.
> 5. **Grounding:** Do not hallucinate. If a concept is not explicitly detailed in the `raw/` sources or prior wiki pages, do not generate fiction to fill the gaps.

---

### 2. The Community "Ingestion" Prompt
When you drop a new research paper or article into your `raw/` folder, you don't just ask Claude to summarize it. The community (specifically in highly-starred repos like `claude-obsidian`) uses this standardized prompt to trigger the compilation loop.

Run this in your terminal via Claude Code:

```bash
Read raw/[filename.pdf]. Extract the core entities, methodologies, and claims. 
Compile this source into the wiki following the CLAUDE.md rules. 
Create 5-10 distinct concept pages, heavily cross-reference them using [[wikilinks]], and update the index and log. 
If any claims in this new source contradict existing wiki pages, add a "[!contradiction]" callout block on the affected pages explaining the discrepancy.
```

---

### 3. The "Linting" Prompt (Crucial for Maintenance)
A major problem the community quickly discovered is "AI-on-AI citation loops"—where the AI generates a slightly imprecise page, and then cites its own imprecision in future queries, compounding the error. 

To prevent the wiki from decaying into a "hallucinatory hairball," developers use a "linting" prompt every week or after every 10 ingests.

Run this in your terminal:

```bash
Run a comprehensive linting pass on the entire wiki/ directory. 
Identify and report the following:
1. Orphaned pages (pages with no [[wikilinks]] pointing to them).
2. Dead links (links pointing to pages that don't exist).
3. Inconsistent terminology (e.g., using both "LLM" and "Large Language Model" as separate pages).
4. Stale claims that have been explicitly superseded by more recent sources in the log.
Do not fix them automatically. Present a report and ask me for permission to execute the fixes.
```

---

### 4. The Query Prompt
Once your wiki has 20+ pages, you stop querying your raw files and start querying your synthesized brain. Because of token limits, the community recommends explicitly restricting Claude's search parameters:

```bash
Using ONLY the files in the wiki/ directory, synthesize an answer to: [Your Question]. 
Do not read the raw/ folder. Base your reasoning strictly on the compounding knowledge we have already compiled. Cite the specific [[concept pages]] you used to generate this answer. 
If the answer is particularly insightful, ask me if you should save it as a new permanent wiki page.
```