// Omnibox routing — mirrors streamlit/ui/components/omnibox.py::omnibox_route.
// A link routes to ingest; anything else is a question for chat.

const URL_RE =
  /(https?:\/\/|www\.|youtu\.?be|youtube\.com|\b\w[\w-]*\.\w{2,}(\/|$))/i;

export type OmniboxRoute = "ingest" | "ask" | null;

export function omniboxRoute(text: string): { kind: OmniboxRoute; text: string } {
  const trimmed = (text ?? "").trim();
  if (!trimmed) return { kind: null, text: "" };
  if (URL_RE.test(trimmed)) return { kind: "ingest", text: trimmed };
  return { kind: "ask", text: trimmed };
}
