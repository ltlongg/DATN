import type { ComponentType } from "react";

/**
 * Một danh nhân. Bản này gán cứng trong `registry.ts` — chưa có bảng `figures` hay
 * router `/api/figures`.
 *
 * `Article` là component thay vì chuỗi HTML là điểm KHÁC duy nhất so với hình dạng
 * response sau này; khi có API, field đó thành `body: string` và một renderer chung đọc
 * nó, còn `FigurePage` (loading / 404 / chrome) không phải sửa gì vì đã đi qua
 * `getFigure()` trả Promise.
 */
export interface Figure {
  slug: string;
  /** Hiện trên thanh trên khi cuộn qua hero. */
  name: string;
  /** Ví dụ "1890 – 1969". */
  lifespan: string;
  /** Mục nhảy nhanh trên thanh trên; `id` khớp id của <section> trong bài. */
  sections: { id: string; label: string }[];
  Article: ComponentType;
}
