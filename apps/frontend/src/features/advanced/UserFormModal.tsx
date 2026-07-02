import { useEffect, useState, type FormEvent } from "react";
import { Modal } from "@/components/Modal";
import type { Role } from "@/types";
import type { UserCreateInput, UserOut, UserUpdateInput } from "@/types/admin";

const ROLES: Role[] = ["teacher", "admin"];

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
  const [role, setRole] = useState<Role>("teacher");
  const [password, setPassword] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [quota, setQuota] = useState("");

  useEffect(() => {
    if (!open) return;
    setEmail(initial?.email ?? "");
    setName(initial?.name ?? "");
    setRole(initial?.role ?? "teacher");
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
      <form onSubmit={submit} className="space-y-3">
        {!isEdit && (
          <>
            <Field label="Email">
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className={inputCls}
              />
            </Field>
            <Field label="Tên">
              <input value={name} onChange={(e) => setName(e.target.value)} required className={inputCls} />
            </Field>
            <Field label="Mật khẩu (≥ 6 ký tự)">
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={6}
                required
                className={inputCls}
              />
            </Field>
          </>
        )}

        <Field label="Vai trò">
          <select value={role} onChange={(e) => setRole(e.target.value as Role)} className={inputCls}>
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </Field>

        {isEdit && (
          <>
            <label className="flex items-center gap-2 text-sm text-ink">
              <input
                type="checkbox"
                checked={isActive}
                disabled={isSelf}
                onChange={(e) => setIsActive(e.target.checked)}
              />
              Tài khoản hoạt động
              {isSelf && (
                <span className="text-xs text-ink-soft">(không thể tự khóa)</span>
              )}
            </label>
            {isEdit && !isActive && (
              <p className="text-xs text-amber-700">
                Token hiện tại của user này sẽ bị từ chối ở lượt gọi API tiếp theo.
              </p>
            )}
            <Field label="Quota câu hỏi/ngày (trống = không giới hạn)">
              <input
                type="number"
                min={0}
                value={quota}
                onChange={(e) => setQuota(e.target.value)}
                className={inputCls}
              />
            </Field>
          </>
        )}

        {error && <p className="text-sm text-rose-700">{error}</p>}

        <div className="flex justify-end gap-2 pt-2">
          <button type="button" onClick={onClose} className="rounded-md px-3 py-2 text-sm text-ink-soft hover:text-ink">
            Huỷ
          </button>
          <button
            type="submit"
            disabled={pending}
            className="rounded-md bg-brand px-4 py-2 text-sm text-brand-fg disabled:opacity-60"
          >
            {pending ? "Đang lưu…" : "Lưu"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

const inputCls =
  "w-full rounded-md border border-paper-border px-3 py-2 outline-none focus:border-brand";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block space-y-1">
      <span className="text-sm font-medium text-ink-soft">{label}</span>
      {children}
    </label>
  );
}
