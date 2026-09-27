import { BrandMark } from "@/components/BrandMark";

/** Logo hệ thống cạnh câu trả lời: ấn triện dáng tròn. */
export function AssistantAvatar() {
  return <BrandMark className="mt-0.5 h-8 w-8 rounded-full" />;
}

/** Chữ cái đầu của người dùng; rỗng thì rơi về "?" thay vì ô trống. */
export function UserAvatar({ name }: { name: string }) {
  const initial = name.trim().charAt(0).toUpperCase() || "?";
  return (
    <span
      aria-hidden
      className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-ink text-xs font-semibold text-paper"
    >
      {initial}
    </span>
  );
}
