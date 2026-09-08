import { useEffect, useMemo, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { getConversation } from "@/api/chat";
import { ChatPanel } from "@/features/chat/ChatPanel";
import { ConversationSidebar } from "@/features/chat/ConversationSidebar";
import { TimelineBar } from "@/features/timeline/TimelineBar";
import { useChat } from "@/features/chat/useChat";
import {
  useRestoreLastConversation,
  writeLastConversation,
} from "@/features/chat/lastConversation";
import {
  conversationsKey,
  useConversations,
  useCreateConversation,
  useDeleteConversation,
  useRenameConversation,
} from "@/features/chat/useConversations";
import { useAuthStore } from "@/store/authStore";
import type { VisualizationPayload } from "@/types";

/** Viz mới nhất có dữ liệu để hiển thị (timeline non-empty). */
function latestVisualization(
  items: { visualization: VisualizationPayload | null }[],
): VisualizationPayload | null {
  for (let i = items.length - 1; i >= 0; i--) {
    const v = items[i].visualization;
    if (v && v.timeline.length > 0) return v;
  }
  return null;
}

/**
 * Khu hỏi đáp: danh sách phiên bên trái, chat ở giữa, thanh dòng thời gian ngang
 * full-width ở đáy khi câu trả lời có sự kiện.
 * Phiên tạo lazy khi gửi câu hỏi đầu. Nav/brand/đăng xuất nằm ở AppSidebar (AppShell).
 *
 * (Bản đồ đã gỡ khỏi hệ thống 2026-09-06 — cùng với nó là bố cục `float` map-nền và nút
 * chuyển bố cục; giờ chỉ còn một bố cục duy nhất.)
 */
export default function AskPage() {
  const queryClient = useQueryClient();

  const { data: conversations, isLoading } = useConversations();
  const createConv = useCreateConversation();
  const renameConv = useRenameConversation();
  const deleteConv = useDeleteConversation();

  const { items, ask, streaming, conversationId, selectConversation, resetConversation } =
    useChat();
  const userId = useAuthStore((s) => s.user?.id);
  // Đọc trong effect bất đồng bộ nên phải qua ref: giá trị lúc effect chạy đã cũ.
  const conversationIdRef = useRef<string | null>(null);

  // Giữ ref ổn định giữa các render (tour theo dõi danh sách này để biết khi nào thực sự
  // có dữ liệu MỚI, không phải mỗi lần token về là thanh thời gian lại nhảy).
  const activeViz = latestVisualization(items);
  const timeline = useMemo(() => activeViz?.timeline ?? [], [activeViz]);

  // Mở lại phiên đang dùng lần trước: state hội thoại chết theo AskPage khi đi sang trang
  // khác, nhưng dữ liệu vẫn nằm trong DB — chỉ là không ai chọn lại giúp.
  const { markHandled } = useRestoreLastConversation(
    userId,
    () => conversationIdRef.current !== null,
    selectConversation,
  );

  // Ghi lại phiên đang mở để lần vào sau khôi phục.
  useEffect(() => {
    conversationIdRef.current = conversationId;
    if (conversationId) writeLastConversation(userId, conversationId);
  }, [conversationId, userId]);

  // Sau mỗi lượt xong -> refresh danh sách phiên (title suy ra + thứ tự updated_at).
  const prevStreaming = useRef(false);
  useEffect(() => {
    if (prevStreaming.current && !streaming) {
      queryClient.invalidateQueries({ queryKey: conversationsKey });
    }
    prevStreaming.current = streaming;
  }, [streaming, queryClient]);

  // Bubble user hiện NGAY; createConv chỉ chạy (nền) khi chưa có phiên (câu đầu).
  function handleSend(text: string) {
    void ask(text, async () => {
      const conv = await createConv.mutateAsync(undefined);
      return conv.id;
    });
  }

  async function handleSelect(id: string) {
    if (id === conversationId) return;
    const detail = await getConversation(id);
    selectConversation(id, detail.messages);
  }

  function handleNew() {
    markHandled(); // chủ động mở phiên mới -> đừng khôi phục đè lên
    writeLastConversation(userId, null);
    resetConversation();
  }

  function handleRename(id: string, title: string) {
    renameConv.mutate({ id, title });
  }

  function handleDelete(id: string) {
    // Xóa phiên đang mở -> quay về màn hình phiên mới rỗng.
    if (id === conversationId) {
      writeLastConversation(userId, null);
      resetConversation();
    }
    deleteConv.mutate(id);
  }

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="flex min-h-0 flex-1 overflow-hidden">
        <ConversationSidebar
          conversations={conversations ?? []}
          activeId={conversationId}
          loading={isLoading}
          onSelect={handleSelect}
          onNew={handleNew}
          onRename={handleRename}
          onDelete={handleDelete}
        />
        {/* Cột chat giới hạn bề ngang + mx-auto: chỗ thừa chia đều 2 bên. */}
        <div className="mx-auto flex w-full max-w-4xl flex-1 flex-col overflow-hidden">
          <ChatPanel items={items} streaming={streaming} onSend={handleSend} />
        </div>
      </div>
      {/* Thanh timeline ngang full-width (kéo dưới cả sidebar + khung chat). */}
      {timeline.length > 0 && <TimelineBar items={timeline} streaming={streaming} />}
    </div>
  );
}
