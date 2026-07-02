import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError } from "@/api/client";
import { createUser, listUsers, updateUser } from "@/api/users";
import { EmptyState } from "@/components/EmptyState";
import { Spinner } from "@/components/Spinner";
import { UserFormModal } from "@/features/advanced/UserFormModal";
import { UserTable } from "@/features/advanced/UserTable";
import { useAuthStore } from "@/store/authStore";
import type { UserCreateInput, UserOut, UserUpdateInput } from "@/types/admin";

const usersKey = ["adm-users"] as const;

export function UsersTab() {
  const qc = useQueryClient();
  const currentUserId = useAuthStore((s) => s.user?.id ?? "");
  const users = useQuery({ queryKey: usersKey, queryFn: listUsers });

  const [form, setForm] = useState<{ open: boolean; user: UserOut | null }>({
    open: false,
    user: null,
  });
  const [error, setError] = useState<string | null>(null);

  const invalidate = () => qc.invalidateQueries({ queryKey: usersKey });
  const createMut = useMutation({ mutationFn: createUser, onSuccess: invalidate });
  const updateMut = useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: UserUpdateInput }) => updateUser(id, patch),
    onSuccess: invalidate,
  });

  async function handleCreate(input: UserCreateInput) {
    setError(null);
    try {
      await createMut.mutateAsync(input);
      setForm({ open: false, user: null });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Không tạo được người dùng.");
    }
  }

  async function handleUpdate(patch: UserUpdateInput) {
    if (!form.user) return;
    setError(null);
    try {
      await updateMut.mutateAsync({ id: form.user.id, patch });
      setForm({ open: false, user: null });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Không cập nhật được người dùng.");
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-ink">Người dùng & quota</h3>
        <button
          onClick={() => {
            setError(null);
            setForm({ open: true, user: null });
          }}
          className="rounded-md bg-brand px-4 py-2 text-sm text-brand-fg hover:bg-brand-dark"
        >
          + Thêm người dùng
        </button>
      </div>

      {users.isLoading ? (
        <Spinner />
      ) : users.isError ? (
        <p className="text-sm text-rose-700">Không tải được danh sách người dùng.</p>
      ) : !users.data || users.data.length === 0 ? (
        <EmptyState>Chưa có người dùng nào.</EmptyState>
      ) : (
        <UserTable
          users={users.data}
          onEdit={(u) => {
            setError(null);
            setForm({ open: true, user: u });
          }}
        />
      )}

      <UserFormModal
        open={form.open}
        initial={form.user}
        currentUserId={currentUserId}
        pending={createMut.isPending || updateMut.isPending}
        error={error}
        onClose={() => setForm({ open: false, user: null })}
        onCreate={handleCreate}
        onUpdate={handleUpdate}
      />
    </div>
  );
}
