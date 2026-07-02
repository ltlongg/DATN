import type { Config } from "tailwindcss";

/**
 * Design tokens (docs/design/frontend-scope.md §Hướng thiết kế):
 * accent đỏ trầm #A4161A, nền be/kem ấm, heading serif + body sans-serif.
 */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: "#A4161A",
          fg: "#ffffff",
          dark: "#7d1013",
          muted: "#c4494c",
        },
        paper: {
          DEFAULT: "#faf6ef", // nền kem ấm
          card: "#fffdf9",
          border: "#e7ddcc",
        },
        ink: {
          DEFAULT: "#2b2620",
          soft: "#5c554a",
        },
      },
      fontFamily: {
        serif: ['"Noto Serif"', "Georgia", "serif"],
        sans: ['"Inter"', "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
} satisfies Config;
