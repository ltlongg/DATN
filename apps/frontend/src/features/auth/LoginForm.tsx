import { useState, type FormEvent } from "react";
import { Lock, Mail } from "lucide-react";
import { AuthInput } from "@/features/auth/AuthInput";
import { useLogin } from "@/features/auth/useLogin";

export function LoginForm() {
  const { submit, pending, error } = useLogin();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    submit(email.trim(), password);
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div className="space-y-1.5">
        <label htmlFor="email" className="block text-sm font-semibold text-ink">
          Email
        </label>
        <AuthInput
          id="email"
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
        <label htmlFor="password" className="block text-sm font-semibold text-ink">
          Mật khẩu
        </label>
        <AuthInput
          id="password"
          type="password"
          autoComplete="current-password"
          required
          placeholder="Nhập mật khẩu"
          icon={<Lock size={18} />}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </div>

      {error && (
        <p role="alert" className="text-sm text-brand">
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={pending}
        className="w-full rounded-md bg-brand py-2 font-medium text-brand-fg transition hover:bg-brand-dark disabled:opacity-60"
      >
        {pending ? "Đang đăng nhập…" : "Đăng nhập"}
      </button>
    </form>
  );
}
