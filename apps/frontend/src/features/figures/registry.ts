import { HoChiMinhArticle } from "./HoChiMinhArticle";
import type { Figure } from "./types";

/**
 * Danh mục danh nhân — gán cứng, chưa có DB.
 *
 * `getFigure` trả Promise dù dữ liệu nằm ngay trong file: để `FigurePage` viết sẵn theo
 * dạng bất đồng bộ, sau này thay ruột bằng `apiGet('/api/figures/' + slug)` là xong,
 * không phải thêm loading/error state vào trang.
 */
const HO_CHI_MINH: Figure = {
  slug: "ho-chi-minh",
  name: "Hồ Chí Minh",
  lifespan: "1890 – 1969",
  sections: [
    { id: "cuocdoi", label: "Cuộc đời" },
    { id: "biennien", label: "Biên niên" },
  ],
  Article: HoChiMinhArticle,
};

const FIGURES: Record<string, Figure> = {
  [HO_CHI_MINH.slug]: HO_CHI_MINH,
};

/** Sidebar bấm "Danh nhân" là vào thẳng bài này: mới có một người, trang danh sách một
 * thẻ thì trống trải. Route vẫn giữ `/danh-nhan/:slug` nên thêm người thứ hai chỉ là
 * thêm một entry vào `FIGURES` rồi mới dựng trang danh sách. */
export const DEFAULT_FIGURE_SLUG = HO_CHI_MINH.slug;

export function getFigure(slug: string): Promise<Figure | null> {
  return Promise.resolve(FIGURES[slug] ?? null);
}
