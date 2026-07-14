const BASE =
  "mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold";

/** Sao 5 cánh, tâm (12,12) trong viewBox 24: đỉnh ngoài r=7, đỉnh trong r=2.75. */
const STAR_PATH =
  "M12 5 L13.62 9.78 L18.66 9.84 L14.62 12.85 L16.11 17.66 L12 14.75 L7.89 17.66 L9.38 12.85 L5.34 9.84 L10.38 9.78 Z";

/** Logo hệ thống cạnh câu trả lời: sao vàng trên nền đỏ brand. */
export function AssistantAvatar() {
  return (
    <span
      aria-hidden
      className={`${BASE} bg-brand shadow-sm ring-1 ring-brand-dark/30`}
    >
      <svg viewBox="0 0 24 24" className="h-[18px] w-[18px]" fill="#FFCD00">
        <path d={STAR_PATH} />
      </svg>
    </span>
  );
}

/** Chữ cái đầu của người dùng; rỗng thì rơi về "?" thay vì ô trống. */
export function UserAvatar({ name }: { name: string }) {
  const initial = name.trim().charAt(0).toUpperCase() || "?";
  return (
    <span aria-hidden className={`${BASE} bg-ink text-paper`}>
      {initial}
    </span>
  );
}
