"""Read the JSONL traces written by merlin/core/telemetry.py.

One trace per library-chat turn (``chat.turn``), per background task
(``ingest.task``) and per agent run outside both (thread titles, Reader chat).

    python scripts/traces.py                    # recent traces, one line each
    python scripts/traces.py list -n 50 --errors
    python scripts/traces.py list --day yesterday
    python scripts/traces.py show last          # the tree of the newest trace
    python scripts/traces.py show be7e --full   # + prompts, outputs, tool results
    python scripts/traces.py html last          # a static page to open in a browser

On the NAS: ``docker compose exec api python scripts/traces.py …``. Standard
library only. The traces dir is ``--dir``, else ``$TRACES_DIR``, else
``./logs/traces``. Past days are ``.jsonl.gz`` and are read the same way.
Times are shown in local time; files are named by UTC day.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
import gzip
import html
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

_FILE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.jsonl(\.gz)?$")
_SHORT = 110  # characters of a tool result / argument list in the tree


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #


def traces_dir(arg: str | None) -> Path:
    return Path(arg or os.environ.get("TRACES_DIR") or "logs/traces")


def day_files(directory: Path) -> list[tuple[str, Path]]:
    """(day, path) per trace file, oldest first; a day may have .jsonl + .gz."""
    if not directory.is_dir():
        return []
    files = [
        (m.group(1), p) for p in directory.iterdir() if (m := _FILE_RE.match(p.name))
    ]
    # .gz before the plain file of the same day: it holds the earlier lines.
    return sorted(files, key=lambda f: (f[0], not f[1].name.endswith(".gz")))


def read_file(path: Path) -> Iterator[dict]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    yield json.loads(line)
                except ValueError:
                    continue  # a line cut short by a crash


def read_days(directory: Path, days: Iterable[str]) -> list[dict]:
    wanted = set(days)
    return [
        span
        for day, path in day_files(directory)
        if day in wanted
        for span in read_file(path)
    ]


def group(spans: Iterable[dict]) -> dict[str, list[dict]]:
    traces: dict[str, list[dict]] = defaultdict(list)
    for span in spans:
        traces[span["trace_id"]].append(span)
    return traces


def find_trace(directory: Path, ref: str) -> tuple[str, list[dict]]:
    """The spans of the trace ``ref`` names: an id prefix, or ``last``.

    Raises LookupError (no match) or ValueError (an ambiguous prefix).
    """
    files = day_files(directory)
    days = sorted({d for d, _ in files}, reverse=True)
    if not days:
        raise LookupError(f"no trace files in {directory}")
    if ref == "last":
        for day in days:
            roots = [
                s for s in read_days(directory, [day]) if s.get("parent_id") is None
            ]
            if roots:
                ref = max(roots, key=lambda s: s.get("end") or "")["trace_id"]
                break
        else:
            raise LookupError("no traces yet")
    ref = ref.lower()
    # Newest day first; a trace that crosses midnight spans two adjacent files.
    for i, day in enumerate(days):
        found = {
            tid for tid in group(read_days(directory, [day])) if tid.startswith(ref)
        }
        if not found:
            continue
        if len(found) > 1:
            raise ValueError(
                f"'{ref}' matches {len(found)} traces: "
                + ", ".join(sorted(t[:12] for t in found))
            )
        tid = found.pop()
        around = days[max(0, i - 1) : i + 2]
        return tid, group(read_days(directory, around))[tid]
    raise LookupError(f"no trace matches '{ref}'")


# --------------------------------------------------------------------------- #
# Summaries
# --------------------------------------------------------------------------- #


def _attrs(span: dict) -> dict:
    return span.get("attributes") or {}


def _op(span: dict) -> str | None:
    return _attrs(span).get("gen_ai.operation.name")


def _is_http(span: dict) -> bool:
    a = _attrs(span)
    return "http.method" in a or "http.request.method" in a


def _local(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts).astimezone()
    except ValueError:
        return None


def fmt_ms(ms: float | None) -> str:
    if ms is None:
        return "…"
    if ms < 1000:
        return f"{ms:.0f}ms"
    if ms < 60_000:
        return f"{ms / 1000:.1f}s"
    return f"{int(ms // 60_000)}m{ms % 60_000 / 1000:02.0f}s"


def _one_line(value, limit: int = _SHORT) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


@dataclass
class TraceSummary:
    trace_id: str
    root: dict | None
    start: datetime | None
    duration_ms: float | None
    name: str
    label: str
    status: str
    model_calls: int = 0
    tools: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    errors: list[dict] = field(default_factory=list)


def _label(root: dict) -> str:
    a = _attrs(root)
    if root["name"] == "chat.turn":
        return f"thread {a.get('thread_id', '?')}"
    if root["name"] == "ingest.task":
        return a.get("raw_input") or a.get("task_type") or a.get("task_id", "")
    if _op(root) == "invoke_agent":
        return f"agent {a.get('gen_ai.agent.name', '?')}"
    if _is_http(root):
        return _http_target(a)
    return ""


def summarize(trace_id: str, spans: list[dict]) -> TraceSummary:
    ids = {s["span_id"] for s in spans}
    roots = [s for s in spans if s.get("parent_id") is None]
    root = min(roots, key=lambda s: s.get("start") or "") if roots else None
    first = min(spans, key=lambda s: s.get("start") or "")
    summary = TraceSummary(
        trace_id=trace_id,
        root=root,
        start=_local((root or first).get("start")),
        duration_ms=root.get("duration_ms") if root else None,
        name=root["name"] if root else "(running)",
        label=_label(root) if root else "",
        status=_attrs(root).get("merlin.status", "") if root else "running",
    )
    if root is None:  # the root is written last: still running, or cut short
        orphans = [s for s in spans if s.get("parent_id") not in ids]
        summary.label = _label(min(orphans, key=lambda s: s.get("start") or ""))
    for span in spans:
        a = _attrs(span)
        if _op(span) == "chat":  # model calls only: agent spans repeat the sums
            summary.model_calls += 1
            summary.input_tokens += a.get("gen_ai.usage.input_tokens") or 0
            summary.output_tokens += a.get("gen_ai.usage.output_tokens") or 0
        elif _op(span) == "execute_tool":
            summary.tools += 1
        if span.get("status") == "ERROR":
            summary.errors.append(span)
    return summary


def summary_line(s: TraceSummary) -> str:
    when = s.start.strftime("%m-%d %H:%M:%S") if s.start else "?"
    calls = f"{s.model_calls} call{'s' if s.model_calls != 1 else ''}"
    tokens = f"{s.input_tokens:,}→{s.output_tokens:,} tok" if s.model_calls else ""
    tools = f"{s.tools} tool{'s' if s.tools != 1 else ''}" if s.tools else ""
    errors = f"✗{len(s.errors)}" if s.errors else ""
    status = s.status if s.status not in ("", "completed") else ""
    return (
        f"{when}  {s.name:<12} {fmt_ms(s.duration_ms):>7}  {calls:<8} "
        f"{tokens:<20} {tools:<8} {errors:<3} {status:<9} "
        f"{_one_line(s.label, 48):<48}  {s.trace_id[:8]}"
    ).rstrip()


# --------------------------------------------------------------------------- #
# Tree (show)
# --------------------------------------------------------------------------- #


def _http_target(a: dict) -> str:
    url = a.get("url.full") or a.get("http.url") or ""
    parts = urlsplit(url)
    target = f"{parts.netloc}{parts.path}"
    return target if len(target) <= 70 else target[:69] + "…"


def describe(span: dict) -> str:
    """The one-line description of a span, after its name and duration."""
    a = _attrs(span)
    op = _op(span)
    bits: list[str] = []
    if span["name"] == "chat.turn":
        bits.append(f"thread={a.get('thread_id')}")
    elif span["name"] == "ingest.task":
        bits += [f"task={str(a.get('task_id', ''))[:8]}", a.get("task_type", "")]
        if a.get("raw_input"):
            bits.append(_one_line(a["raw_input"], 70))
    elif op == "invoke_agent":
        bits.append(f"[{a.get('gen_ai.agent.name', '?')}]")
    elif op == "chat":
        model = a.get("gen_ai.response.model") or a.get("gen_ai.request.model")
        if str(model) not in span["name"]:  # the span is named "chat <model>"
            bits.append(str(model))
        tok = f"{a.get('gen_ai.usage.input_tokens', 0)}→"
        tok += f"{a.get('gen_ai.usage.output_tokens', 0)} tok"
        extra = [
            f"{k.rsplit('.', 1)[-1].removesuffix('_tokens')} {v}"
            for k, v in a.items()
            if k.startswith("gen_ai.usage.details.")
            and k.endswith(("cache_read_tokens", "reasoning_tokens"))
            and v
        ]
        bits.append(tok + (f" ({', '.join(extra)})" if extra else ""))
        reasons = a.get("gen_ai.response.finish_reasons")
        if reasons and reasons != ["stop"]:
            bits.append(f"finish={','.join(reasons)}")
    elif op == "execute_tool":
        bits.append(str(a.get("gen_ai.tool.name", "?")))
        if "tool_arguments" in a:
            bits.append(_one_line(a["tool_arguments"], 70))
        if "tool_response" in a:
            bits.append("→ " + _one_line(a["tool_response"], 60))
    elif _is_http(span):
        method = a.get("http.request.method") or a.get("http.method")
        code = a.get("http.response.status_code") or a.get("http.status_code")
        bits += [_http_target(a), f"→ {code}" if code else ""]
        if span["name"] != method:
            bits.insert(0, str(method))
    if a.get("merlin.status") and a["merlin.status"] != "completed":
        bits.append(f"status={a['merlin.status']}")
    if span.get("status") == "ERROR":
        bits.append(f"✗ {_one_line(span.get('status_message') or 'error', 90)}")
    return "  ".join(b for b in bits if b)


def children_map(spans: list[dict]) -> tuple[list[dict], dict[str, list[dict]]]:
    ids = {s["span_id"] for s in spans}
    kids: dict[str, list[dict]] = defaultdict(list)
    tops = []
    for span in spans:
        parent = span.get("parent_id")
        (kids[parent].append(span) if parent in ids else tops.append(span))
    order = lambda s: s.get("start") or ""  # noqa: E731
    for siblings in kids.values():
        siblings.sort(key=order)
    return sorted(tops, key=order), kids


def render_parts(messages) -> list[str]:
    """Readable lines for a GenAI message list (input/output/all messages)."""
    if not isinstance(messages, list):
        return [str(messages)]
    out: list[str] = []
    for message in messages:
        if not isinstance(message, dict):
            out.append(str(message))
            continue
        role = message.get("role", "?")
        for part in message.get("parts") or []:
            kind = part.get("type")
            if kind in ("text", "thinking"):
                head = role if kind == "text" else f"{role} (thinking)"
                body = part.get("content", "(content not recorded)")
            elif kind == "tool_call":
                head = f"{role} → {part.get('name')}"
                body = _jsonish(part.get("arguments"))
            elif kind == "tool_call_response":
                head = f"tool {part.get('name')} result"
                body = _jsonish(part.get("result", "(content not recorded)"))
            else:
                head, body = f"{role} ({kind})", _jsonish(part)
            out.append(f"[{head}]")
            out.extend(str(body).splitlines() or [""])
    return out


def _jsonish(value) -> str:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return value
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, indent=2)


def full_sections(span: dict) -> list[tuple[str, list[str]]]:
    """The long-form content of a span, for --full and the HTML page."""
    a = _attrs(span)
    sections: list[tuple[str, list[str]]] = []

    def add(title: str, lines: list[str]) -> None:
        if lines:
            sections.append((title, lines))

    if "gen_ai.system_instructions" in a:
        add(
            "instructions",
            render_parts(
                [{"role": "system", "parts": a["gen_ai.system_instructions"]}]
            ),
        )
    if "gen_ai.input.messages" in a:
        omitted = a.get("merlin.input_messages_omitted")
        title = "input" + (
            f" (new at this step; {omitted} earlier omitted)" if omitted else ""
        )
        add(title, render_parts(a["gen_ai.input.messages"]))
    if "gen_ai.output.messages" in a:
        add("output", render_parts(a["gen_ai.output.messages"]))
    if "tool_arguments" in a:
        add("arguments", _jsonish(a["tool_arguments"]).splitlines())
    if "tool_response" in a:
        add("result", _jsonish(a["tool_response"]).splitlines())
    if "final_result" in a:
        add("final result", _jsonish(a["final_result"]).splitlines())
    for event in span.get("events") or []:
        ea = event.get("attributes") or {}
        if event.get("name") == "exception":
            add(
                f"exception {ea.get('exception.type', '')}",
                str(ea.get("exception.stacktrace") or ea.get("exception.message"))
                .rstrip()
                .splitlines(),
            )
    return sections


def render_tree(spans: list[dict], *, full: bool = False) -> list[str]:
    tops, kids = children_map(spans)
    lines: list[str] = []

    def walk(span: dict, prefix: str, last: bool, top: bool) -> None:
        branch = "" if top else ("└─ " if last else "├─ ")
        head = f"{span['name']}  {fmt_ms(span.get('duration_ms'))}"
        lines.append(f"{prefix}{branch}{head}  {describe(span)}".rstrip())
        child_prefix = prefix + ("" if top else ("   " if last else "│  "))
        if full:
            for title, body in full_sections(span):
                lines.append(f"{child_prefix}┊ ── {title} ──")
                lines.extend(f"{child_prefix}┊ {line}" for line in body)
        children = kids.get(span["span_id"], [])
        for i, child in enumerate(children):
            walk(child, child_prefix, i == len(children) - 1, False)

    for span in tops:
        walk(span, "", True, True)
    return lines


# --------------------------------------------------------------------------- #
# HTML
# --------------------------------------------------------------------------- #

_CSS = """
:root { --bg:#fbfaf7; --fg:#1d1c1a; --muted:#6b6862; --line:#e4e1da;
  --panel:#ffffff; --code:#f3f1ec; --err:#b42318; --accent:#2f5d8a; }
@media (prefers-color-scheme: dark) { :root { --bg:#151515; --fg:#e8e6e1;
  --muted:#9a968f; --line:#2c2b29; --panel:#1c1c1b; --code:#232220;
  --err:#f97066; --accent:#84adda; } }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--fg);
  font:14px/1.45 ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 980px; margin: 0 auto; padding: 20px 16px 48px; }
h1 { font-size: 18px; margin: 0 0 4px; }
.meta { color: var(--muted); margin: 0 0 16px; font-size: 13px;
  overflow-wrap: anywhere; }
details { border-left: 2px solid var(--line); margin: 2px 0 2px 6px;
  padding-left: 10px; }
details.err { border-left-color: var(--err); }
summary { cursor: pointer; padding: 3px 0; list-style-position: outside;
  overflow-wrap: anywhere; }
.name { font-weight: 600; }
.dur { color: var(--accent); font-variant-numeric: tabular-nums;
  margin: 0 6px; }
.desc { color: var(--muted); }
details.err > summary .desc { color: var(--err); }
.inner-err { color: var(--err); font-size: 12px; margin-left: 6px; }
.tools { display: flex; gap: 8px; margin: 0 0 12px; }
button { font: inherit; font-size: 12px; color: var(--fg); background: var(--panel);
  border: 1px solid var(--line); border-radius: 6px; padding: 3px 10px;
  cursor: pointer; }
.leaf { padding: 3px 0 3px 18px; margin-left: 6px; border-left: 2px solid
  var(--line); overflow-wrap: anywhere; }
.sec { margin: 4px 0 8px; background: var(--panel); border: 1px solid
  var(--line); border-radius: 6px; }
.sec > summary { padding: 4px 10px; font-size: 12px; color: var(--muted);
  list-style-position: inside;
  text-transform: uppercase; letter-spacing: .04em; }
.sec { border-left: 1px solid var(--line); padding-left: 0; margin-left: 0; }
pre { margin: 0; padding: 8px 10px; background: var(--code); white-space:
  pre-wrap; overflow-wrap: anywhere; font: 12px/1.5 ui-monospace, SFMono-Regular,
  Menlo, Consolas, monospace; border-radius: 0 0 6px 6px; }
"""


def render_html(trace_id: str, spans: list[dict]) -> str:
    summary = summarize(trace_id, spans)
    tops, kids = children_map(spans)
    esc = html.escape
    by_id = {s["span_id"]: s for s in spans}
    # Spans with a failed span somewhere below them: marked and opened, so an
    # error inside a collapsed model call is never out of sight.
    err_above: set[str] = set()
    for span in summary.errors:
        parent = span.get("parent_id")
        while parent in by_id and parent not in err_above:
            err_above.add(parent)
            parent = by_id[parent].get("parent_id")

    def head(span: dict) -> str:
        inner = (
            '<span class="inner-err">✗ error inside</span>'
            if span["span_id"] in err_above
            else ""
        )
        return (
            f'<span class="name">{esc(span["name"])}</span>'
            f'<span class="dur">{esc(fmt_ms(span.get("duration_ms")))}</span>'
            f'<span class="desc">{esc(describe(span))}</span>{inner}'
        )

    def node(span: dict, depth: int) -> str:
        children = kids.get(span["span_id"], [])
        sections = full_sections(span)
        err = ' class="err"' if span.get("status") == "ERROR" else ""
        if not children and not sections:
            return f'<div class="leaf">{head(span)}</div>'
        # Open the top two levels: the root and the agent run / model calls.
        opened = " open" if depth < 2 or span["span_id"] in err_above else ""
        body = "".join(
            f'<details class="sec"><summary>{esc(title)}</summary>'
            f"<pre>{esc(chr(10).join(lines))}</pre></details>"
            for title, lines in sections
        )
        body += "".join(node(c, depth + 1) for c in children)
        return f"<details{err}{opened}><summary>{head(span)}</summary>{body}</details>"

    when = summary.start.strftime("%Y-%m-%d %H:%M:%S %Z") if summary.start else "?"
    meta = " · ".join(
        bit
        for bit in (
            when,
            fmt_ms(summary.duration_ms),
            f"{summary.model_calls} model calls",
            f"{summary.input_tokens:,}→{summary.output_tokens:,} tokens",
            f"{summary.tools} tools",
            (
                f"{len(summary.errors)} error{'s' if len(summary.errors) > 1 else ''}"
                if summary.errors
                else ""
            ),
            f"trace {trace_id}",
        )
        if bit
    )
    title = f"{summary.name} {summary.label}".strip()
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>Trace {esc(trace_id[:8])}</title><style>{_CSS}</style></head>"
        f"<body><main><h1>{esc(_one_line(title, 120))}</h1>"
        f'<p class="meta">{esc(meta)}</p>'
        '<div class="tools"><button type="button" data-open="1">Expand all</button>'
        '<button type="button" data-open="">Collapse all</button></div>'
        + "".join(node(s, 0) for s in tops)
        + "</main><script>document.querySelectorAll('button[data-open]')"
        ".forEach(b=>b.onclick=()=>document.querySelectorAll('details')"
        ".forEach(d=>d.open=!!b.dataset.open))</script></body></html>\n"
    )


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _resolve_day(value: str) -> str:
    today = datetime.now(UTC).date()
    if value == "today":
        return today.isoformat()
    if value == "yesterday":
        return (today - timedelta(days=1)).isoformat()
    return date.fromisoformat(value).isoformat()


def cmd_list(args) -> int:
    directory = traces_dir(args.dir)
    files = day_files(directory)
    if not files:
        print(f"No trace files in {directory}", file=sys.stderr)
        return 1
    if args.day:
        day = _resolve_day(args.day)
        nxt = (date.fromisoformat(day) + timedelta(days=1)).isoformat()
        spans = read_days(directory, [day, nxt])
    else:
        days = sorted({d for d, _ in files})[-3:]  # recent: enough for -n
        spans = read_days(directory, days)
    summaries = [summarize(t, s) for t, s in group(spans).items()]
    if args.day:
        summaries = [
            s
            for s in summaries
            if s.start and s.start.astimezone(UTC).date().isoformat() == day
        ]
    if args.errors:
        summaries = [s for s in summaries if s.errors]
    summaries.sort(key=lambda s: s.start or datetime.min.replace(tzinfo=UTC))
    for s in summaries[-args.n :]:
        print(summary_line(s))
    if not summaries:
        print("No matching traces.", file=sys.stderr)
    return 0


def _load(args) -> tuple[str, list[dict]] | None:
    try:
        return find_trace(traces_dir(args.dir), args.trace)
    except (LookupError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return None


def cmd_show(args) -> int:
    loaded = _load(args)
    if loaded is None:
        return 2
    trace_id, spans = loaded
    print(summary_line(summarize(trace_id, spans)))
    print()
    print("\n".join(render_tree(spans, full=args.full)))
    return 0


def cmd_html(args) -> int:
    loaded = _load(args)
    if loaded is None:
        return 2
    trace_id, spans = loaded
    out = Path(args.out) if args.out else traces_dir(args.dir) / "html"
    if out.suffix != ".html":
        out = out / f"{trace_id[:8]}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_html(trace_id, spans), encoding="utf-8")
    print(out)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dir", help="traces dir (default: $TRACES_DIR)")
    sub = parser.add_subparsers(dest="cmd")

    p_list = sub.add_parser("list", help="recent traces, one line each")
    p_list.add_argument("-n", type=int, default=20, help="how many (default 20)")
    p_list.add_argument("--day", help="today | yesterday | YYYY-MM-DD (UTC)")
    p_list.add_argument("--errors", action="store_true", help="only with errors")
    p_list.set_defaults(func=cmd_list)

    p_show = sub.add_parser("show", help="one trace as a tree")
    p_show.add_argument("trace", help="trace id prefix, or 'last'")
    p_show.add_argument(
        "--full", action="store_true", help="prompts, outputs, full tool results"
    )
    p_show.set_defaults(func=cmd_show)

    p_html = sub.add_parser("html", help="one trace as a static HTML page")
    p_html.add_argument("trace", help="trace id prefix, or 'last'")
    p_html.add_argument("--out", help="file or dir (default: <dir>/html/)")
    p_html.set_defaults(func=cmd_html)

    args = parser.parse_args(argv)
    if args.cmd is None:  # bare `traces.py` = list
        args = parser.parse_args([*(argv or sys.argv[1:]), "list"])
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
