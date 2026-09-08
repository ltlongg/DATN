import { DienBienPhuBoard } from "./DienBienPhuBoard";
import type { Campaign } from "./types";

/**
 * Danh mục chiến dịch — gán cứng, chưa có DB. Giống hệt cách làm ở
 * `features/figures/registry.ts`: `getCampaign` trả Promise dù dữ liệu nằm ngay trong file,
 * để sau này thay ruột bằng `apiGet('/api/campaigns/' + slug)` là xong.
 */
const DIEN_BIEN_PHU: Campaign = {
  slug: "dien-bien-phu-1954",
  name: "Điện Biên Phủ",
  period: "13/3 – 7/5/1954",
  Board: DienBienPhuBoard,
};

const CAMPAIGNS: Record<string, Campaign> = {
  [DIEN_BIEN_PHU.slug]: DIEN_BIEN_PHU,
};

/** Sidebar bấm "Chiến dịch" là vào thẳng bản này: mới có một chiến dịch, trang danh sách
 * một thẻ thì trống trải. Route vẫn giữ `/chien-dich/:slug` nên thêm chiến dịch thứ hai
 * chỉ là thêm một entry vào `CAMPAIGNS` rồi mới dựng trang danh sách. */
export const DEFAULT_CAMPAIGN_SLUG = DIEN_BIEN_PHU.slug;

export function getCampaign(slug: string): Promise<Campaign | null> {
  return Promise.resolve(CAMPAIGNS[slug] ?? null);
}
