import type { ReactNode } from "react";

/** Tiêu đề + mô tả 1 dòng cho mỗi trang (nav dọc, mỗi chức năng 1 route). `actions` là slot
 * phải cho nút thao tác (vd "Thêm tài liệu"). */
export function PageHeader({
  title,
  desc,
  actions,
}: {
  title: string;
  desc?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight text-ink">{title}</h1>
        {desc && <p className="mt-1 max-w-3xl text-sm text-ink-soft">{desc}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}
