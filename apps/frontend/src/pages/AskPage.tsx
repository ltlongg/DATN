import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { getConversation } from "@/api/chat";
import { ChatPanel } from "@/features/chat/ChatPanel";
import { ConversationSidebar } from "@/features/chat/ConversationSidebar";
import { VizPanel } from "@/features/chat/VizPanel";
import { useChat } from "@/features/chat/useChat";
import {
  conversationsKey,
  useConversations,
  useCreateConversation,
} from "@/features/chat/useConversations";
import { useChatUiStore } from "@/store/chatUiStore";
import type { VisualizationPayload } from "@/types";

/** Viz mới nhất có dữ liệu để hiển thị (markers hoặc timeline non-empty). */
function latestVisualization(
  items: { visualization: VisualizationPayload | null }[],
): VisualizationPayload | null {
  for (let i = items.length - 1; i >= 0; i--) {
    const v = items[i].visualization;
    if (v && (v.markers.length > 0 || v.timeline.length > 0)) return v;
  }
  return null;
}

/** Khu hỏi đáp: sidebar phiên + khung chat. Phiên tạo lazy khi gửi câu hỏi đầu.
 * Nav/brand/đăng xuất nằm ở AppSidebar (AppShell). */
export default function AskPage() {
  const queryClient = useQueryClient();

  const { data: conversations, isLoading } = useConversations();
  const createConv = useCreateConversation();

  const { items, ask, streaming, conversationId, selectConversation, resetConversation } =
    useChat();

  const vizPanelOpen = useChatUiStore((s) => s.vizPanelOpen);
  const activeViz = latestVisualization(items);
  const showViz = vizPanelOpen && activeViz !== null;

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

  return (
    <div className="flex h-full overflow-hidden">
      <ConversationSidebar
        conversations={conversations ?? []}
        activeId={conversationId}
        loading={isLoading}
        onSelect={handleSelect}
        onNew={resetConversation}
      />
      <div className="flex flex-1 overflow-hidden">
        <div
          className={
            showViz ? "flex w-1/2 flex-col overflow-hidden" : "mx-auto flex w-full max-w-3xl flex-1 flex-col overflow-hidden"
          }
        >
          <ChatPanel items={items} streaming={streaming} onSend={handleSend} />
        </div>
        {showViz && activeViz && <VizPanel visualization={activeViz} />}
      </div>
    </div>
  );
}
