import { useEffect, useRef } from "react";
import { MessageBubble } from "@/features/chat/MessageBubble";
import type { ChatItem } from "@/features/chat/chatReducer";

/** Danh sách message, tự cuộn xuống cuối khi có nội dung mới. */
export function MessageList({ items }: { items: ChatItem[] }) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [items]);

  return (
    <div className="flex-1 space-y-4 overflow-y-auto px-4 py-6">
      {items.map((item) => (
        <MessageBubble key={item.id} item={item} />
      ))}
      <div ref={endRef} />
    </div>
  );
}
