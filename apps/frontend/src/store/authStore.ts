import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import { resolveStorage } from "@/store/storage";
import type { User } from "@/types";

interface AuthState {
  token: string | null;
  user: User | null;
  setAuth: (token: string, user: User) => void;
  setUser: (user: User) => void;
  clear: () => void;
  isAdmin: () => boolean;
}

/**
 * Auth state persist localStorage. `client.ts` đọc token qua getState() (ngoài React),
 * RequireAuth/RoleGuard đọc qua hook để điều hướng.
 */
export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      setAuth: (token, user) => set({ token, user }),
      setUser: (user) => set({ user }),
      clear: () => set({ token: null, user: null }),
      isAdmin: () => get().user?.role === "admin",
    }),
    { name: "vfs-auth", storage: createJSONStorage(resolveStorage) },
  ),
);
