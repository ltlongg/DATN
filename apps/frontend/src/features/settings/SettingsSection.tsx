import { useId, type ReactNode } from "react";

/** Khung 1 mục trên trang Cài đặt: tiêu đề + mô tả ngắn ở đầu thẻ, nội dung bên dưới. */
export function SettingsSection({
  title,
  desc,
  children,
}: {
  title: string;
  desc: string;
  children: ReactNode;
}) {
  const headingId = useId();
  return (
    <section className="card" aria-labelledby={headingId}>
      <div className="border-b border-paper-border px-6 py-4">
        <h2 id={headingId} className="font-sans text-base font-semibold text-ink">
          {title}
        </h2>
        <p className="mt-0.5 text-sm text-ink-soft">{desc}</p>
      </div>
      <div className="px-6 py-5">{children}</div>
    </section>
  );
}
