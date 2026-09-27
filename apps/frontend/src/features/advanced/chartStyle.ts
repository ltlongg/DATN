import { palette } from "@/theme";

/** Style chung cho trục + tooltip recharts ở trang Chi phí (recharts không đọc class Tailwind). */
export const CHART_AXIS = {
  fontSize: 11,
  tick: { fill: palette.ink.soft },
  axisLine: false,
  tickLine: false,
} as const;

const compact = new Intl.NumberFormat("vi-VN", { notation: "compact" });

/** Trục giá trị: số rút gọn kiểu Việt (25 N, 1,6 Tr) thay vì 1600000. */
export const CHART_Y_AXIS = {
  ...CHART_AXIS,
  width: 48,
  tickFormatter: (v: number) => compact.format(v),
};

export const CHART_TOOLTIP = {
  cursor: { fill: palette.paper.sunken },
  contentStyle: {
    borderRadius: 8,
    border: `1px solid ${palette.paper.border}`,
    fontSize: 12,
  },
  formatter: (value: number) => value.toLocaleString("vi-VN"),
};
