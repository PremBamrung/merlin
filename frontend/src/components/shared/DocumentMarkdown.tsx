import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface DocumentMarkdownProps {
  content: string
}

export default function DocumentMarkdown({ content }: DocumentMarkdownProps) {
  return (
    <div className="doc-markdown">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>
        {content}
      </ReactMarkdown>
      <style>{`
        .doc-markdown {
          font-size: 14px;
          line-height: 1.65;
          color: var(--text-muted);
        }
        .doc-markdown > *:first-child { margin-top: 0; }
        .doc-markdown > *:last-child { margin-bottom: 0; }
        .doc-markdown p { margin: 0 0 12px; }
        .doc-markdown ul, .doc-markdown ol { margin: 0 0 12px; padding-left: 20px; }
        .doc-markdown li { margin-bottom: 4px; }
        .doc-markdown h1, .doc-markdown h2, .doc-markdown h3, .doc-markdown h4 {
          color: var(--text);
          margin: 18px 0 8px;
          line-height: 1.3;
        }
        .doc-markdown h1 { font-size: 24px; }
        .doc-markdown h2 { font-size: 20px; }
        .doc-markdown h3 { font-size: 17px; }
        .doc-markdown h4 { font-size: 15px; }
        .doc-markdown a { color: var(--accent); text-decoration: none; }
        .doc-markdown a:hover { text-decoration: underline; }
        .doc-markdown code {
          font-family: var(--font-mono);
          font-size: 12px;
          background: var(--bg-2);
          border: 1px solid var(--border);
          border-radius: 5px;
          padding: 1px 5px;
        }
        .doc-markdown pre {
          margin: 0 0 12px;
          background: var(--bg-2);
          border: 1px solid var(--border);
          border-radius: 8px;
          padding: 10px 12px;
          overflow-x: auto;
        }
        .doc-markdown pre code {
          background: transparent;
          border: 0;
          border-radius: 0;
          padding: 0;
        }
        .doc-markdown blockquote {
          margin: 0 0 12px;
          padding-left: 12px;
          border-left: 3px solid var(--border-accent);
          color: var(--text-subtle);
        }
        .doc-markdown hr {
          border: 0;
          border-top: 1px solid var(--border);
          margin: 14px 0;
        }
      `}</style>
    </div>
  )
}
