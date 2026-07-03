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
    <div className="space-y-2 text-ink">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p className="leading-relaxed">{children}</p>,
          strong: ({ children }) => (
            <strong className="font-semibold text-ink">{children}</strong>
          ),
          em: ({ children }) => <em className="italic">{children}</em>,
          ul: ({ children }) => <ul className="list-disc space-y-1 pl-5">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal space-y-1 pl-5">{children}</ol>,
          li: ({ children }) => <li className="leading-relaxed">{children}</li>,
          h1: ({ children }) => (
            <h1 className="mt-1 font-serif text-lg font-bold text-ink">{children}</h1>
          ),
          h2: ({ children }) => (
            <h2 className="mt-1 font-serif text-base font-bold text-ink">{children}</h2>
          ),
          h3: ({ children }) => (
            <h3 className="mt-1 font-serif text-sm font-bold text-ink">{children}</h3>
          ),
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
              className="text-brand underline hover:text-brand-dark"
            >
              {children}
            </a>
          ),
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-paper-border pl-3 text-ink-soft">
              {children}
            </blockquote>
          ),
          code: ({ children }) => (
            <code className="rounded bg-paper px-1 py-0.5 font-mono text-[0.85em] text-ink">
              {children}
            </code>
          ),
          table: ({ children }) => (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-sm">{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th className="border border-paper-border bg-paper px-2 py-1 text-left font-semibold">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border border-paper-border px-2 py-1 align-top">{children}</td>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
