import { useState, type FormEvent } from "react";
import { Lock, Mail, User } from "lucide-react";
import { AuthInput } from "@/features/auth/AuthInput";
import { useRegister } from "@/features/auth/useRegister";

const LABEL_CLASS = "block text-sm font-semibold text-ink";

export function RegisterForm() {
  const { submit, pending, error } = useRegister();
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [mismatch, setMismatch] = useState(false);

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (password !== confirm) {
      setMismatch(true);
      return;
    }
    submit(email.trim(), name.trim(), password);
  }

  // Lỗi khớp mật khẩu (client) ưu tiên hiển thị trước lỗi API.
  const shownError = mismatch ? "Mật khẩu xác nhận không khớp." : error;

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div className="space-y-1.5">
        <label htmlFor="reg-name" className={LABEL_CLASS}>
          Họ tên
        </label>
        <AuthInput
          id="reg-name"
          type="text"
          autoComplete="name"
          required
          minLength={2}
          maxLength={80}
          placeholder="Nguyễn Văn A"
          icon={<User size={18} />}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </div>

      <div className="space-y-1.5">
        <label htmlFor="reg-email" className={LABEL_CLASS}>
          Email
        </label>
        <AuthInput
          id="reg-email"
          type="email"
          autoComplete="username"
          required
          placeholder="email@example.com"
          icon={<Mail size={18} />}
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </div>

      <div className="space-y-1.5">
        <label htmlFor="reg-password" className={LABEL_CLASS}>
          Mật khẩu
        </label>
        <AuthInput
          id="reg-password"
          type="password"
          autoComplete="new-password"
          required
          minLength={8}
          placeholder="Ít nhất 8 ký tự"
          icon={<Lock size={18} />}
          value={password}
          onChange={(e) => {
            setPassword(e.target.value);
            if (mismatch) setMismatch(false);
          }}
        />
        <p className="text-xs text-ink-soft">Tối thiểu 8 ký tự.</p>
      </div>

      <div className="space-y-1.5">
        <label htmlFor="reg-confirm" className={LABEL_CLASS}>
          Mật khẩu xác nhận
        </label>
        <AuthInput
          id="reg-confirm"
          type="password"
          autoComplete="new-password"
          required
          minLength={8}
          placeholder="Nhập lại mật khẩu"
          icon={<Lock size={18} />}
          value={confirm}
          onChange={(e) => {
            setConfirm(e.target.value);
            if (mismatch) setMismatch(false);
          }}
        />
      </div>

      {shownError && (
        <p role="alert" className="text-sm text-brand">
          {shownError}
        </p>
      )}

      <button
        type="submit"
        disabled={pending}
        className="w-full rounded-md bg-brand py-2 font-medium text-brand-fg transition hover:bg-brand-dark disabled:opacity-60"
      >
        {pending ? "Đang tạo tài khoản…" : "Đăng ký"}
      </button>
    </form>
  );
}
