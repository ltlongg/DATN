import type { Citation } from "@/types";

/**
 * Gộp citation theo mục (`heading_path`) cho khối Nguồn — xem docs/plan/citation-viewer-plan.md §3.
 *
 * Vì UI đã bỏ tên file + số dòng, hai citation cùng một mục sẽ render RA HAI DÒNG Y HỆT NHAU
 * nếu không gộp. Gộp ở đây là để ĐÚNG, không phải để đẹp. Đơn vị tương tác vẫn là từng chip
 * `[n]` (1 chip = 1 chunk); nhóm chỉ là cách xếp chỗ.
 *
 * Thuần, không I/O -> test không cần render.
 */

const SEP = "\u0000"; // ký tự không xuất hiện trong heading -> ghép/tách key an toàn
const UNKNOWN_TITLE = "Không rõ mục";

export interface CitationChip {
  /** Số hiển thị: thứ tự GỐC trong mảng citations (1-based). Gộp không đánh số lại — `[n]`
   * phải khớp với `[n]` mà câu trả lời nhắc tới. */
  n: number;
  citation: Citation;
}

export interface CitationGroup {
  title: string;
  chips: CitationChip[];
}

export interface GroupedCitations {
  groups: CitationGroup[];
  /** Tiền tố heading chung của mọi citation -> render 1 lần ở dòng chân. Rỗng = nguồn rải
   * rác nhiều chương, không có gì chung để rút ra. */
  commonPath: string[];
}

/** Tiền tố chung dài nhất của các path. Rỗng nếu có path rỗng hoặc phần tử đầu đã khác nhau. */
function longestCommonPrefix(paths: string[][]): string[] {
  const [first, ...rest] = paths;
  if (!first) return [];
  let len = first.length;
  for (const path of rest) {
    len = Math.min(len, path.length);
    for (let i = 0; i < len; i++) {
      if (path[i] !== first[i]) {
        len = i;
        break;
      }
    }
    if (len === 0) return [];
  }
  return first.slice(0, len);
}

export function groupCitations(citations: Citation[]): GroupedCitations {
  const chipsByPath = new Map<string, CitationChip[]>();
  citations.forEach((citation, index) => {
    const key = citation.heading_path.join(SEP);
    const chips = chipsByPath.get(key);
    if (chips) chips.push({ n: index + 1, citation });
    else chipsByPath.set(key, [{ n: index + 1, citation }]);
  });

  // Map giữ thứ tự chèn -> nhóm xếp theo chip nhỏ nhất -> đọc từ trên xuống vẫn [1] [2] [3]…
  const entries = [...chipsByPath.entries()].map(([key, chips]) => ({
    path: key === "" ? [] : key.split(SEP),
    chips,
  }));

  let commonPath = longestCommonPrefix(entries.map((e) => e.path));
  // Tiền tố chung nuốt trọn một path -> nhóm đó không còn chữ nào làm tiêu đề -> lùi 1 cấp,
  // nhường cấp cuối cho tiêu đề. (Chỉ tối đa 1 path bằng đúng tiền tố chung.)
  if (commonPath.length > 0 && entries.some((e) => e.path.length === commonPath.length)) {
    commonPath = commonPath.slice(0, -1);
  }

  const groups = entries.map(({ path, chips }) => ({
    title: path.slice(commonPath.length).join(" › ") || UNKNOWN_TITLE,
    chips,
  }));
  return { groups, commonPath };
}
