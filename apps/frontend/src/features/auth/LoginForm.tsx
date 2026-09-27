import { useState, type FormEvent } from "react";
import { Lock, Mail } from "lucide-react";
import { Alert } from "@/components/Alert";
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
      <div>
        <label htmlFor="email" className="label">
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

      <div>
        <label htmlFor="password" className="label">
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

      {error && <Alert>{error}</Alert>}

      <button
        type="submit"
        disabled={pending}
        className="btn btn-primary mt-2 h-11 w-full"
      >
        {pending ? "Đang đăng nhập…" : "Đăng nhập"}
      </button>
    </form>
  );
}
