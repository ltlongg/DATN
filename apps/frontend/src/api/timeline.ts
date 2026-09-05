import { apiFetch } from "@/api/client";
import type { TimelineCardsResponse } from "@/types/timeline";

/** Feed biên niên toàn kho (chỉ cần đăng nhập). Hình dạng phản hồi khớp `listEvents` để
 * dùng chung `getNextPageParam` của useInfiniteQuery. */
export function listTimelineCards(params: {
  limit?: number;
  offset?: number;
}): Promise<TimelineCardsResponse> {
  return apiFetch<TimelineCardsResponse>("/api/timeline/events", { query: { ...params } });
}
