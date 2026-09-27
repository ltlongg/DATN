/**
 * Bảng màu DUY NHẤT của app (hướng "Heritage hiện đại": đỏ son + vàng đồng trên nền ngà).
 * `tailwind.config.ts` import để sinh class; chỗ không dùng được class (recharts, canvas của
 * đồ thị) import thẳng từ đây — không rải hex trong component.
 */
export const palette = {
  brand: {
    DEFAULT: "#B3261E", // đỏ son
    dark: "#8C1D18",
    soft: "#FBEBE9",
    fg: "#FFFFFF",
  },
  gold: {
    DEFAULT: "#B7832F", // vàng đồng — điểm nhấn, không dùng cho chữ nhỏ (tương phản thấp)
    bright: "#F2C14E", // sao trên ấn triện
    soft: "#F7EFDF",
  },
  paper: {
    DEFAULT: "#F7F6F3", // nền app
    card: "#FFFFFF",
    sunken: "#F2F0EB", // hover / nền phụ
    border: "#E7E3DC",
  },
  ink: {
    DEFAULT: "#1F1B16",
    soft: "#5F584F",
    faint: "#8F887E", // placeholder / chữ phụ không quan trọng
  },
  night: {
    DEFAULT: "#1C1917", // sidebar tối
    raised: "#292524",
    border: "#3A3531",
    text: "#D6D3D1",
    muted: "#A8A29E",
  },
} as const;
