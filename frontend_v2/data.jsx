/* global React */
// Mock data — realistic knowledge-base sample
const VIDEOS = [
  {
    id: 'v1',
    type: 'youtube',
    title: "Andrej Karpathy: The State of GPT",
    channel: 'Microsoft Build',
    duration: '42:12',
    views: '1.2M',
    added: '2h ago',
    summary: "A pragmatic tour of the full LLM training pipeline — from pretraining and instruction tuning to RLHF, plus when to use which model. Karpathy emphasizes treating LLMs as 'System 1' thinkers: fast, intuitive, and prone to mistakes when asked to reason in one shot.",
    tags: ['llm-research', 'fundamentals'],
    topics: [
      { t: '00:00', text: 'Pretraining: compression as intelligence' },
      { t: '08:14', text: 'Why base models are not assistants' },
      { t: '17:30', text: 'Supervised fine-tuning vs RLHF' },
      { t: '26:02', text: 'Prompt engineering as System 2 scaffolding' },
      { t: '33:48', text: 'Tool use, retrieval, and the agent frontier' },
    ],
  },
  {
    id: 'v2',
    type: 'youtube',
    title: "Let's build GPT: from scratch, in code, spelled out.",
    channel: 'Andrej Karpathy',
    duration: '1:56:20',
    views: '4.8M',
    added: 'yesterday',
    summary: "Four hours compressed into two: Karpathy implements a nanoGPT from nothing — tokenizer, attention, MLP blocks, training loop. The payoff is intuition, not a production model.",
    tags: ['llm-research', 'pytorch'],
    topics: [
      { t: '00:00', text: 'Reading Shakespeare, character by character' },
      { t: '22:11', text: 'Self-attention from first principles' },
      { t: '58:44', text: 'Multi-head and residual connections' },
    ],
  },
  {
    id: 'v3',
    type: 'youtube',
    title: 'Rust for the impatient',
    channel: 'No Boilerplate',
    duration: '11:48',
    views: '890K',
    added: '3d',
    summary: "A brisk manifesto: ownership, borrowing, and lifetimes aren't obstacles, they're the point. If you've been putting off Rust, this is the nudge.",
    tags: ['rust'],
    topics: [],
  },
];

const BLOGS = [
  {
    id: 'b1',
    type: 'blog',
    title: 'Building LLM Applications for Production',
    author: 'Chip Huyen',
    site: 'huyenchip.com',
    readTime: '22 min',
    added: 'today',
    summary: "A candid catalog of what breaks when LLMs meet production: eval gaps, prompt drift, data pipelines, cost surprises, and why a good vector DB alone won't save you.",
    tags: ['llm-research', 'mlops'],
  },
  {
    id: 'b2',
    type: 'blog',
    title: 'The design of everyday colors',
    author: 'Oliver Reichenstein',
    site: 'ia.net',
    readTime: '9 min',
    added: '2d',
    summary: "Why the best interface palettes feel like paper and ink: a meditation on contrast, restraint, and the honest warmth of a single accent.",
    tags: ['design-systems'],
  },
];

const REDDITS = [
  {
    id: 'r1',
    type: 'reddit',
    title: 'What setups are you running for a local-first second brain in 2026?',
    subreddit: 'r/PKMS',
    comments: 182,
    added: '5h',
    summary: "Thread consensus: local SQLite + embedding index, synced via Syncthing. Obsidian vaults dominate, but a growing cohort is rolling their own Streamlit/FastAPI frontends.",
    tags: ['pkm'],
  },
];

const ALL_SOURCES = [...VIDEOS, ...BLOGS, ...REDDITS];

const TAGS = [
  { name: 'llm-research', color: '#c9a9ff', count: 34 },
  { name: 'rust', color: '#e8a87c', count: 22 },
  { name: 'design-systems', color: '#8db089', count: 18 },
  { name: 'woodworking', color: '#d99547', count: 14 },
  { name: 'longevity', color: '#7ba2c9', count: 9 },
  { name: 'pytorch', color: '#b8a0ff', count: 12 },
  { name: 'mlops', color: '#a8c4e8', count: 8 },
  { name: 'pkm', color: '#e8c47c', count: 6 },
  { name: 'fundamentals', color: '#9ec9b8', count: 15 },
];

Object.assign(window, { VIDEOS, BLOGS, REDDITS, ALL_SOURCES, TAGS });
