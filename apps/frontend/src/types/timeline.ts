/** Types trang Dòng lịch sử. Mirror apps/backend/app/schemas/timeline.py.
 *
 * Tên `TimelineCardItem` (không phải `TimelineCard`) để khỏi đụng component cùng tên ở
 * `features/explore/TimelineCard.tsx`. Khác `TimelineItem` trong `types/index.ts` — cái
 * đó là thanh timeline bên hỏi đáp.
 */

export interface TimelineCardItem {
  event_id: string;
  label: string;
  summary: string;
  /** Luôn có: backend lọc sẵn event không có mốc / mốc không parse được. */
  time_start: string;
  time_end?: string | null;
  locations: string[];
  confidence: string;
}

export interface TimelineCardsResponse {
  items: TimelineCardItem[];
  total: number;
  limit: number;
  offset: number;
}
