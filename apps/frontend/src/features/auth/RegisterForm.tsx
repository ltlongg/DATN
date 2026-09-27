import { useState, type FormEvent } from "react";
import { Lock, Mail, User } from "lucide-react";
import { Alert } from "@/components/Alert";
import { AuthInput } from "@/features/auth/AuthInput";
import { useRegister } from "@/features/auth/useRegister";

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
      <div>
        <label htmlFor="reg-name" className="label">
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

      <div>
        <label htmlFor="reg-email" className="label">
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

      <div>
        <label htmlFor="reg-password" className="label">
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
      </div>

      <div>
        <label htmlFor="reg-confirm" className="label">
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

      {shownError && <Alert>{shownError}</Alert>}

      <button
        type="submit"
        disabled={pending}
        className="btn btn-primary mt-2 h-11 w-full"
      >
        {pending ? "Đang tạo tài khoản…" : "Đăng ký"}
      </button>
    </form>
  );
}
