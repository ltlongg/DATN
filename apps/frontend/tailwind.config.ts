import type { Config } from "tailwindcss";
import { palette } from "./src/theme";

/**
 * Design tokens — bảng màu sống ở `src/theme.ts` (dùng chung với chart/canvas).
 * Heading serif (Noto Serif) + body sans tối ưu dấu tiếng Việt (Be Vietnam Pro).
 */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: palette,
      fontFamily: {
        serif: ['"Noto Serif"', "Georgia", "serif"],
        sans: ['"Be Vietnam Pro"', "system-ui", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 2px rgb(28 25 23 / 0.04), 0 1px 3px rgb(28 25 23 / 0.06)",
        pop: "0 12px 32px -8px rgb(28 25 23 / 0.18), 0 4px 8px -4px rgb(28 25 23 / 0.08)",
      },
      keyframes: {
        "fade-in": { from: { opacity: "0" }, to: { opacity: "1" } },
        "pop-in": {
          from: { opacity: "0", transform: "translate(-50%, -48%) scale(0.98)" },
          to: { opacity: "1", transform: "translate(-50%, -50%) scale(1)" },
        },
      },
      animation: {
        "fade-in": "fade-in 150ms ease-out",
        "pop-in": "pop-in 180ms ease-out",
      },
    },
  },
  plugins: [],
} satisfies Config;
