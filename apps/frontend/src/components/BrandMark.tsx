/** Sao 5 cánh, tâm (12,12) trong viewBox 24: đỉnh ngoài r=7, đỉnh trong r=2.75. */
const STAR_PATH =
  "M12 5 L13.62 9.78 L18.66 9.84 L14.62 12.85 L16.11 17.66 L12 14.75 L7.89 17.66 L9.38 12.85 L5.34 9.84 L10.38 9.78 Z";

/** Dấu nhận diện "ấn triện": sao vàng trên nền đỏ son. `className` quyết định cỡ + dáng
 * (vd `h-9 w-9 rounded-lg` ở sidebar, `h-8 w-8 rounded-full` làm avatar trợ lý). */
export function BrandMark({ className = "h-9 w-9 rounded-lg" }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={`flex shrink-0 items-center justify-center bg-brand shadow-sm ring-1 ring-inset ring-black/10 ${className}`}
    >
      <svg viewBox="0 0 24 24" className="h-[70%] w-[70%] fill-gold-bright">
        <path d={STAR_PATH} />
      </svg>
    </span>
  );
}
