import { useEffect, useState, type FormEvent } from "react";
import { Alert } from "@/components/Alert";
import { Field } from "@/components/Field";
import { Modal } from "@/components/Modal";
import type { Role } from "@/types";
import type { UserCreateInput, UserOut, UserUpdateInput } from "@/types/admin";

const ROLES: Role[] = ["user", "admin"];

/**
 * Tạo/sửa user. Sửa: đổi role/khóa/quota. Chặn tự khóa (BE trả 400 self_lock_forbidden) ->
 * disable ô khóa trên chính hàng admin đang đăng nhập.
 */
export function UserFormModal({
  open,
  initial,
  currentUserId,
  pending,
  error,
  onClose,
  onCreate,
  onUpdate,
}: {
  open: boolean;
  initial: UserOut | null;
  currentUserId: string;
  pending: boolean;
  error: string | null;
  onClose: () => void;
  onCreate: (input: UserCreateInput) => void;
  onUpdate: (patch: UserUpdateInput) => void;
}) {
  const isEdit = initial !== null;
  const isSelf = initial?.id === currentUserId;

  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState<Role>("user");
  const [password, setPassword] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [quota, setQuota] = useState("");

  useEffect(() => {
    if (!open) return;
    setEmail(initial?.email ?? "");
    setName(initial?.name ?? "");
    setRole(initial?.role ?? "user");
    setPassword("");
    setIsActive(initial?.is_active ?? true);
    setQuota(initial?.question_quota == null ? "" : String(initial.question_quota));
  }, [open, initial]);

  function submit(e: FormEvent) {
    e.preventDefault();
    if (isEdit) {
      onUpdate({
        role,
        is_active: isActive,
        question_quota: quota.trim() === "" ? null : Math.max(0, Number(quota)),
      });
    } else {
      if (!email.trim() || !name.trim() || password.length < 6) return;
      onCreate({ email: email.trim(), name: name.trim(), role, password });
    }
  }

  return (
    <Modal
      open={open}
      onOpenChange={(o) => !o && onClose()}
      title={isEdit ? "Sửa người dùng" : "Thêm người dùng"}
    >
      <form onSubmit={submit} className="space-y-4">
        {!isEdit && (
          <>
            <Field label="Email">
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="input"
              />
            </Field>
            <Field label="Tên">
              <input value={name} onChange={(e) => setName(e.target.value)} required className="input" />
            </Field>
            <Field label="Mật khẩu (≥ 6 ký tự)">
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={6}
                required
                className="input"
              />
            </Field>
          </>
        )}

        <Field label="Vai trò">
          <select value={role} onChange={(e) => setRole(e.target.value as Role)} className="input">
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </Field>

        {isEdit && (
          <>
            <label className="flex items-center gap-2.5 text-sm font-medium text-ink">
              <input
                type="checkbox"
                className="h-4 w-4 accent-brand"
                checked={isActive}
                disabled={isSelf}
                onChange={(e) => setIsActive(e.target.checked)}
              />
              Tài khoản hoạt động
              {isSelf && (
                <span className="text-xs font-normal text-ink-soft">(không thể tự khóa)</span>
              )}
            </label>
            {isEdit && !isActive && (
              <Alert tone="warning">
                Token hiện tại của user này sẽ bị từ chối ở lượt gọi API tiếp theo.
              </Alert>
            )}
            <Field label="Quota câu hỏi/ngày (trống = không giới hạn)">
              <input
                type="number"
                min={0}
                value={quota}
                onChange={(e) => setQuota(e.target.value)}
                className="input"
              />
            </Field>
          </>
        )}

        {error && <Alert>{error}</Alert>}

        <div className="flex justify-end gap-2 pt-2">
          <button type="button" onClick={onClose} className="btn btn-secondary">
            Huỷ
          </button>
          <button type="submit" disabled={pending} className="btn btn-primary">
            {pending ? "Đang lưu…" : "Lưu"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
