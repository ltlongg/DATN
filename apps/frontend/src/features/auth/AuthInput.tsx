import { useState, type InputHTMLAttributes, type ReactNode } from "react";
import { Eye, EyeOff } from "lucide-react";

interface AuthInputProps extends InputHTMLAttributes<HTMLInputElement> {
  /** Icon hiển thị ở đầu ô (dùng icon lucide, size ~18). */
  icon: ReactNode;
}

/**
 * Ô nhập dùng chung cho form auth: icon gợi ý ở đầu ô + placeholder mờ khi chưa nhập.
 * Nếu `type="password"` thì tự thêm nút con mắt ẩn/hiện mật khẩu ở cuối ô.
 */
export function AuthInput({ icon, type, ...props }: AuthInputProps) {
  const [show, setShow] = useState(false);
  const isPassword = type === "password";
  const inputType = isPassword ? (show ? "text" : "password") : type;

  return (
    <div className="relative">
      <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-soft">
        {icon}
      </span>
      <input
        type={inputType}
        className={`w-full rounded-lg border border-paper-border bg-white py-2.5 pl-10 ${
          isPassword ? "pr-10" : "pr-3.5"
        } text-ink outline-none transition placeholder:text-ink-soft/60 focus:border-brand focus:ring-2 focus:ring-brand/20`}
        {...props}
      />
      {isPassword && (
        <button
          type="button"
          onClick={() => setShow((s) => !s)}
          tabIndex={-1}
          aria-label={show ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-soft transition hover:text-ink"
        >
          {show ? <EyeOff size={18} /> : <Eye size={18} />}
        </button>
      )}
    </div>
  );
}
