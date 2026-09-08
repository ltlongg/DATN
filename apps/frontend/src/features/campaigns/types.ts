import type { ComponentType } from "react";

/**
 * Một chiến dịch. Bản này gán cứng trong `registry.ts` — chưa có bảng `campaigns` hay
 * router `/api/campaigns`. Hình dạng đặt song song với `features/figures/types.ts` để hai
 * chuyên đề đi cùng một đường khi có API.
 *
 * `Board` là component chứ không phải chuỗi HTML, và khác `Figure.Article` ở chỗ nó CÓ
 * trạng thái (đang ở cảnh nào, đang chạy hay dừng). Khi có API, thứ tải về là dữ liệu cảnh
 * (`chapters`, `sites`), còn `Board` vẫn là component đọc dữ liệu đó — `CampaignPage`
 * không phải sửa vì đã đi qua `getCampaign()` trả Promise.
 */
export interface Campaign {
  slug: string;
  name: string;
  /** Ví dụ "13/3 – 7/5/1954". */
  period: string;
  Board: ComponentType;
}
