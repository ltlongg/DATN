/**
 * Đọc/hiển thị mốc thời gian lịch sử. Dùng chung cho thanh timeline bên hỏi đáp
 * (`TimelineBar`) và trang Dòng lịch sử (`features/explore`) — tránh nhân bản logic parse.
 *
 * `time_start`/`time_end` là TEXT ở 6 độ mịn có thật trong kho (xem plan §2):
 *   `1954-05-07` · `1856-09` · `1945` · `40` · `XII` · `179 TCN` (và `III TCN`)
 * cùng đúng một mốc rác `9 tháng` (LLM lấy độ dài làm mốc).
 *
 * Hai nguyên tắc:
 * 1. `parseYearFrac` dùng ĐÚNG quy ước khoá của SQL (`reconcile.time_sort_key`) — thế kỷ
 *    lấy năm đầu, TCN thành số âm, không parse được thì `null` — để FE và DB không lệch
 *    thứ tự nhau.
 * 2. Hiển thị giữ ĐÚNG ĐỘ MỊN NGUỒN: `XII` hiện là "thế kỷ XII", KHÔNG quy thành năm
 *    1101 (số đó chỉ để xếp chỗ).
 */

const ROMAN_VALUES: Record<string, number> = { I: 1, V: 5, X: 10, L: 50, C: 100, D: 500, M: 1000 };

const BC_SUFFIX = " TCN";
/** Năm 1-4 chữ số, tuỳ chọn -tháng, tuỳ chọn -ngày (hậu tố TCN đã cắt trước khi khớp). */
const YEAR_RE = /^(\d{1,4})(?:-(\d{1,2}))?(?:-(\d{1,2}))?$/;
const ROMAN_RE = /^[IVXLCDM]+$/;

interface ParsedTime {
  /** Số La Mã -> số thế kỷ; ngược lại null. */
  century: number | null;
  year: number;
  month: number | null;
  day: number | null;
  isBC: boolean;
}

function parse(raw: string | null | undefined): ParsedTime | null {
  if (!raw) return null;
  let text = raw.trim();

  const isBC = text.endsWith(BC_SUFFIX);
  if (isBC) text = text.slice(0, -BC_SUFFIX.length).trim();

  const m = YEAR_RE.exec(text);
  if (m) {
    return {
      century: null,
      year: Number(m[1]),
      month: m[2] ? Number(m[2]) : null,
      day: m[3] ? Number(m[3]) : null,
      isBC,
    };
  }

  if (ROMAN_RE.test(text)) {
    let total = 0;
    let prev = 0;
    for (let i = text.length - 1; i >= 0; i--) {
      const value = ROMAN_VALUES[text[i]];
      total += value < prev ? -value : value;
      prev = Math.max(prev, value);
    }
    // Thế kỷ -> năm ĐẦU thế kỷ, cùng quy ước khoá SQL (XII -> 1101, III TCN -> -300).
    return { century: total, year: isBC ? total * 100 : (total - 1) * 100 + 1, month: null, day: null, isBC };
  }

  return null;
}

/** Mốc -> "năm thập phân" để so sánh/đặt vị trí trên trục. Không parse được -> null. */
export function parseYearFrac(t: string | null | undefined): number | null {
  const p = parse(t);
  if (!p) return null;
  // Phần lẻ luôn CỘNG vào kể cả TCN: trong năm 179 TCN thì tháng 3 muộn hơn đầu năm.
  const offset = ((p.month ?? 1) - 1) / 12 + ((p.day ?? 1) - 1) / 365;
  return (p.isBC ? -p.year : p.year) + offset;
}

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

/** Mốc -> nhãn đọc được, giữ đúng độ mịn nguồn. Không parse được -> in nguyên văn. */
export function shortTime(t: string): string {
  const raw = t.trim();
  const p = parse(raw);
  if (!p) return raw;
  if (p.century !== null) return `thế kỷ ${raw}`; // "XII" -> "thế kỷ XII", giữ cả hậu tố TCN
  if (p.day !== null) return `${pad(p.day)}/${pad(p.month as number)}/${p.year}`;
  if (p.month !== null) return `${pad(p.month)}/${p.year}`;
  return raw; // năm trần (kể cả "179 TCN") giữ nguyên
}

/** Nhãn thô: bỏ ngày/tháng nhưng giữ nguyên TCN/thế kỷ. Dùng cho hai đầu một cụm mốc. */
export function yearLabel(t: string): string {
  const p = parse(t);
  if (!p) return t.trim();
  if (p.century !== null) return shortTime(t);
  return p.isBC ? `${p.year}${BC_SUFFIX}` : String(p.year);
}

/** "07/05/1954" hoặc "1946 – 1954". Mốc cuối trùng/thiếu -> chỉ mốc đầu. */
export function rangeLabel(start: string, end?: string | null): string {
  if (end && end !== start) return `${shortTime(start)} – ${shortTime(end)}`;
  return shortTime(start);
}

/**
 * Độ dài khoảng: "8 năm" / "8 tháng" / "14 ngày". Trả null khi không phải khoảng thật
 * (thiếu mốc cuối, mốc không parse được, mốc cuối không sau mốc đầu) — 88% sự kiện là
 * sự kiện ĐIỂM, không bịa độ dài cho chúng.
 */
export function durationLabel(start: string, end?: string | null): string | null {
  const from = parseYearFrac(start);
  const to = parseYearFrac(end);
  if (from === null || to === null) return null;

  const years = to - from;
  if (years <= 0) return null;
  if (years >= 1) return `${Math.round(years)} năm`;

  const months = Math.round(years * 12);
  if (months >= 1) return `${months} tháng`;

  const days = Math.round(years * 365);
  return days >= 1 ? `${days} ngày` : null;
}
