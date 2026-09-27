import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * Render markdown câu trả lời (LLM hay dùng **đậm**, danh sách, bảng). Không có
 * @tailwindcss/typography nên map từng thẻ sang class Tailwind theo tông giấy/mực của app.
 * Dùng cho cả lúc đang stream: markdown dở dang (vd `**` chưa đóng) tự render thô rồi
 * chuyển sang đậm khi token đóng cặp tới — react-markdown parse lại mỗi lần content đổi.
 */
export function Markdown({ content }: { content: string }) {
  return (
    <div className="space-y-3 leading-7 text-ink">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p>{children}</p>,
          strong: ({ children }) => <strong className="font-semibold text-ink">{children}</strong>,
          em: ({ children }) => <em className="italic">{children}</em>,
          ul: ({ children }) => (
            <ul className="list-disc space-y-1.5 pl-5 marker:text-brand/60">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal space-y-1.5 pl-5 marker:font-medium marker:text-brand/70">
              {children}
            </ol>
          ),
          li: ({ children }) => <li className="pl-1">{children}</li>,
          h1: ({ children }) => (
            <h1 className="pt-1 font-serif text-xl font-semibold text-ink">{children}</h1>
          ),
          h2: ({ children }) => (
            <h2 className="pt-1 font-serif text-lg font-semibold text-ink">{children}</h2>
          ),
          h3: ({ children }) => (
            <h3 className="pt-1 font-serif text-base font-semibold text-ink">{children}</h3>
          ),
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
              className="font-medium text-brand underline decoration-brand/30 underline-offset-2 hover:decoration-brand"
            >
              {children}
            </a>
          ),
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-gold bg-gold-soft/50 py-2 pl-4 pr-3 text-ink-soft">
              {children}
            </blockquote>
          ),
          code: ({ children }) => (
            <code className="rounded bg-paper-sunken px-1.5 py-0.5 font-mono text-[0.85em] text-ink">
              {children}
            </code>
          ),
          table: ({ children }) => (
            <div className="overflow-x-auto rounded-lg border border-paper-border">
              <table className="w-full border-collapse text-sm">{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th className="border-b border-paper-border bg-paper-sunken px-3 py-2 text-left font-semibold">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border-b border-paper-border/70 px-3 py-2 align-top">{children}</td>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
