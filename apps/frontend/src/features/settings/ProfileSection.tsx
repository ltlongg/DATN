import { useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { updateProfile } from "@/api/auth";
import { ApiError } from "@/api/client";
import { Alert } from "@/components/Alert";
import { SettingsSection } from "@/features/settings/SettingsSection";
import { useApplyUser } from "@/features/settings/useMe";
import type { User } from "@/types";

/** Họ tên sửa được; email chỉ hiển thị (định danh đăng nhập, chưa có xác minh email). */
export function ProfileSection({ user }: { user: User }) {
  const applyUser = useApplyUser();
  const [name, setName] = useState(user.name);
  const save = useMutation({ mutationFn: updateProfile, onSuccess: applyUser });

  const trimmed = name.trim();
  const unchanged = trimmed === user.name;

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    save.mutate({ name: trimmed });
  }

  return (
    <SettingsSection title="Thông tin cá nhân" desc="Tên hiển thị trong ứng dụng và email đăng nhập.">
      <form onSubmit={onSubmit} className="space-y-4">
        <div>
          <label htmlFor="profile-name" className="label">
            Họ tên
          </label>
          <input
            id="profile-name"
            type="text"
            autoComplete="name"
            required
            minLength={2}
            maxLength={80}
            className="input h-10"
            value={name}
            onChange={(e) => {
              setName(e.target.value);
              save.reset();
            }}
          />
        </div>

        <div>
          <label htmlFor="profile-email" className="label">
            Email
          </label>
          <input id="profile-email" type="email" className="input h-10" value={user.email} disabled />
          <span className="help">
            {user.has_password
              ? "Email dùng để đăng nhập nên không thể thay đổi."
              : "Tài khoản đăng nhập bằng Google — email không thể thay đổi."}
          </span>
        </div>

        {save.isError && (
          <Alert>
            {save.error instanceof ApiError ? save.error.message : "Không lưu được, thử lại sau."}
          </Alert>
        )}
        {save.isSuccess && <Alert tone="success">Đã lưu thông tin cá nhân.</Alert>}

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={unchanged || trimmed.length < 2 || save.isPending}
            className="btn btn-primary"
          >
            {save.isPending ? "Đang lưu…" : "Lưu thay đổi"}
          </button>
        </div>
      </form>
    </SettingsSection>
  );
}
