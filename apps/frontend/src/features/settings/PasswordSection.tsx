import { useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { Lock } from "lucide-react";
import { changePassword } from "@/api/auth";
import { ApiError } from "@/api/client";
import { Alert } from "@/components/Alert";
import { AuthInput } from "@/features/auth/AuthInput";
import { SettingsSection } from "@/features/settings/SettingsSection";

/** Đổi mật khẩu — chỉ render cho tài khoản có mật khẩu (xem SettingsPage). */
export function PasswordSection() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [mismatch, setMismatch] = useState(false);
  const save = useMutation({
    mutationFn: changePassword,
    onSuccess: () => {
      setCurrent("");
      setNext("");
      setConfirm("");
    },
  });

  function edit(setter: (v: string) => void) {
    return (v: string) => {
      setter(v);
      setMismatch(false);
      save.reset();
    };
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (next !== confirm) {
      setMismatch(true);
      return;
    }
    save.mutate({ current_password: current, new_password: next });
  }

  // Lỗi khớp mật khẩu (client) ưu tiên hiển thị trước lỗi API — như RegisterForm.
  const error = mismatch
    ? "Mật khẩu xác nhận không khớp."
    : save.isError
      ? save.error instanceof ApiError
        ? save.error.message
        : "Không đổi được mật khẩu, thử lại sau."
      : null;

  const fields = [
    { id: "pw-current", label: "Mật khẩu hiện tại", value: current, set: edit(setCurrent), auto: "current-password", min: undefined, ph: "Nhập mật khẩu đang dùng" },
    { id: "pw-new", label: "Mật khẩu mới", value: next, set: edit(setNext), auto: "new-password", min: 8, ph: "Ít nhất 8 ký tự" },
    { id: "pw-confirm", label: "Xác nhận mật khẩu mới", value: confirm, set: edit(setConfirm), auto: "new-password", min: 8, ph: "Nhập lại mật khẩu mới" },
  ];

  return (
    <SettingsSection title="Mật khẩu" desc="Đổi mật khẩu đăng nhập. Cần nhập mật khẩu hiện tại để xác nhận.">
      <form onSubmit={onSubmit} className="space-y-4">
        {fields.map((f) => (
          <div key={f.id}>
            <label htmlFor={f.id} className="label">
              {f.label}
            </label>
            <AuthInput
              id={f.id}
              type="password"
              autoComplete={f.auto}
              required
              minLength={f.min}
              placeholder={f.ph}
              icon={<Lock size={18} />}
              value={f.value}
              onChange={(e) => f.set(e.target.value)}
            />
          </div>
        ))}

        {error && <Alert>{error}</Alert>}
        {save.isSuccess && <Alert tone="success">Đã đổi mật khẩu.</Alert>}

        <div className="flex justify-end">
          <button type="submit" disabled={save.isPending} className="btn btn-primary">
            {save.isPending ? "Đang lưu…" : "Đổi mật khẩu"}
          </button>
        </div>
      </form>
    </SettingsSection>
  );
}
