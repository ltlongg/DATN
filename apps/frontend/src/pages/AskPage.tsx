import { useEffect, useMemo, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Columns2, Map as MapIcon, Menu } from "lucide-react";
import { getConversation } from "@/api/chat";
import { ChatPanel } from "@/features/chat/ChatPanel";
import { ConversationDrawer } from "@/features/chat/ConversationDrawer";
import { ConversationSidebar } from "@/features/chat/ConversationSidebar";
import { VizPanel } from "@/features/chat/VizPanel";
import { EventMap } from "@/features/map/EventMap";
import { TimelineBar } from "@/features/timeline/TimelineBar";
import { useChat } from "@/features/chat/useChat";
import {
  conversationsKey,
  useConversations,
  useCreateConversation,
  useDeleteConversation,
  useRenameConversation,
} from "@/features/chat/useConversations";
import { useChatUiStore, type LayoutMode } from "@/store/chatUiStore";
import type { VisualizationPayload } from "@/types";

/** Lề fitBounds ở layout float: chừa bề ngang card chat (trái) + thanh timeline (dưới)
 * để marker không bị che. */
const FLOAT_BOUNDS_PADDING: google.maps.Padding = {
  left: 570,
  top: 72,
  right: 72,
  bottom: 190,
};

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

/** Nút chuyển bố cục. Nền đục để đọc được cả khi đè lên map lẫn lên khung chat. */
function LayoutToggle({
  mode,
  onChange,
  className,
}: {
  mode: LayoutMode;
  onChange: (mode: LayoutMode) => void;
  className: string;
}) {
  const toFloat = mode === "split";
  const label = toFloat ? "Bản đồ toàn nền" : "Tách đôi màn hình";
  return (
    <button
      onClick={() => onChange(toFloat ? "float" : "split")}
      title={label}
      aria-label={label}
      className={`flex items-center gap-1.5 rounded-lg border border-paper-border bg-paper-card px-2.5 py-1.5 text-xs font-medium text-ink-soft shadow-md transition hover:border-brand hover:text-brand ${className}`}
    >
      {toFloat ? <MapIcon size={15} /> : <Columns2 size={15} />}
      <span className="hidden sm:inline">{label}</span>
    </button>
  );
}

/**
 * Khu hỏi đáp. Hai bố cục (nhớ qua reload, `chatUiStore.layoutMode`):
 * - `float` (mặc định): bản đồ làm NỀN toàn màn hình, card chat nổi bên trái, danh sách
 *   phiên thu vào drawer (☰), timeline nổi ở đáy.
 * - `split`: chat một bên, bản đồ (VizPanel) một bên, timeline docked full-width.
 * Phiên tạo lazy khi gửi câu hỏi đầu. Nav/brand/đăng xuất nằm ở AppSidebar (AppShell).
 */
export default function AskPage() {
  const queryClient = useQueryClient();

  const { data: conversations, isLoading } = useConversations();
  const createConv = useCreateConversation();
  const renameConv = useRenameConversation();
  const deleteConv = useDeleteConversation();

  const { items, ask, streaming, conversationId, selectConversation, resetConversation } =
    useChat();

  const layoutMode = useChatUiStore((s) => s.layoutMode);
  const setLayoutMode = useChatUiStore((s) => s.setLayoutMode);
  const drawerOpen = useChatUiStore((s) => s.convDrawerOpen);
  const setDrawerOpen = useChatUiStore((s) => s.setConvDrawerOpen);
  const vizPanelOpen = useChatUiStore((s) => s.vizPanelOpen);
  const openViz = useChatUiStore((s) => s.openViz);

  // Giữ ref ổn định giữa các render (map/tour theo dõi danh sách này để biết khi nào
  // thực sự có dữ liệu MỚI, không phải mỗi lần token về là camera lại giật).
  const activeViz = latestVisualization(items);
  const markers = useMemo(() => activeViz?.markers ?? [], [activeViz]);
  const timeline = useMemo(() => activeViz?.timeline ?? [], [activeViz]);
  const showViz = layoutMode === "split" && vizPanelOpen && activeViz !== null;
  const activeTitle =
    conversations?.find((c) => c.id === conversationId)?.title ?? "Cuộc trò chuyện mới";

  // Có viz MỚI -> mở panel bản đồ (layout split). Theo DỮ LIỆU chứ không theo nguồn:
  // phiên nạp lại từ DB cũng phải hiện bản đồ, không riêng câu trả lời vừa stream về.
  // User bấm Đóng thì panel đóng thật (activeViz không đổi -> effect không chạy lại).
  useEffect(() => {
    if (activeViz) openViz();
  }, [activeViz, openViz]);

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
    setDrawerOpen(false);
    if (id === conversationId) return;
    const detail = await getConversation(id);
    selectConversation(id, detail.messages);
  }

  function handleNew() {
    setDrawerOpen(false);
    resetConversation();
  }

  function handleRename(id: string, title: string) {
    renameConv.mutate({ id, title });
  }

  function handleDelete(id: string) {
    // Xóa phiên đang mở -> quay về màn hình phiên mới rỗng.
    if (id === conversationId) resetConversation();
    deleteConv.mutate(id);
  }

  const sidebar = (
    <ConversationSidebar
      conversations={conversations ?? []}
      activeId={conversationId}
      loading={isLoading}
      onSelect={handleSelect}
      onNew={handleNew}
      onRename={handleRename}
      onDelete={handleDelete}
    />
  );

  if (layoutMode === "float") {
    return (
      <div className="relative h-full overflow-hidden">
        <div className="absolute inset-0">
          <EventMap markers={markers} boundsPadding={FLOAT_BOUNDS_PADDING} />
        </div>

        {/* Lớp nổi: pointer-events-none để cử chỉ ở vùng trống rơi xuống map;
            từng khối con tự bật lại pointer-events. */}
        <div className="pointer-events-none absolute inset-0 flex flex-col p-4">
          <div className="flex min-h-0 flex-1">
            <div className="pointer-events-auto flex w-[520px] max-w-full flex-col overflow-hidden rounded-2xl border border-paper-border bg-paper-card shadow-xl">
              <div className="flex items-center gap-2 border-b border-paper-border px-3 py-2">
                <button
                  onClick={() => setDrawerOpen(true)}
                  aria-label="Danh sách cuộc trò chuyện"
                  title="Danh sách cuộc trò chuyện"
                  className="rounded-md p-1.5 text-ink-soft hover:bg-paper hover:text-brand"
                >
                  <Menu size={18} />
                </button>
                <span className="truncate text-sm font-medium text-ink">{activeTitle}</span>
              </div>
              <div className="min-h-0 flex-1">
                <ChatPanel items={items} streaming={streaming} onSend={handleSend} />
              </div>
            </div>
          </div>

          {timeline.length > 0 && (
            <div className="pointer-events-auto mt-4">
              <TimelineBar items={timeline} variant="overlay" streaming={streaming} />
            </div>
          )}
        </div>

        <LayoutToggle
          mode={layoutMode}
          onChange={setLayoutMode}
          className="absolute right-4 top-4 z-30"
        />

        <ConversationDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)}>
          {sidebar}
        </ConversationDrawer>
      </div>
    );
  }

  return (
    <div className="relative flex h-full flex-col overflow-hidden">
      <div className="flex min-h-0 flex-1 overflow-hidden">
        {sidebar}
        <div className="flex flex-1 overflow-hidden">
          <div
            className={
              showViz
                ? "flex w-1/2 flex-col overflow-hidden"
                : // Không có viz -> cột chat giới hạn bề ngang + mx-auto: chỗ thừa chia đều 2 bên.
                  "mx-auto flex w-full max-w-4xl flex-1 flex-col overflow-hidden"
            }
          >
            <ChatPanel items={items} streaming={streaming} onSend={handleSend} />
          </div>
          {showViz && activeViz && <VizPanel visualization={activeViz} />}
        </div>
      </div>
      {/* Thanh timeline ngang full-width (kéo dưới cả sidebar + khung chat). */}
      {timeline.length > 0 && <TimelineBar items={timeline} streaming={streaming} />}

      <LayoutToggle
        mode={layoutMode}
        onChange={setLayoutMode}
        className="absolute right-3 top-2 z-30"
      />
    </div>
  );
}
