import type { ReactNode } from "react";

/** Tiêu đề + mô tả 1 dòng cho mỗi trang admin (nav dọc, mỗi chức năng 1 route). `actions`
 * là slot phải cho nút thao tác (vd "+ Thêm tài liệu"). */
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
    <div className="flex items-start justify-between gap-4">
      <div>
        <h2 className="text-xl font-semibold text-ink">{title}</h2>
        {desc && <p className="mt-0.5 text-sm text-ink-soft">{desc}</p>}
      </div>
      {actions && <div className="shrink-0">{actions}</div>}
    </div>
  );
}
