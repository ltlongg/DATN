import { Navigate, Outlet } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";

/** Không phải admin -> đá về khu user (/). BE cũng chặn cứng require_admin (403). */
export function RoleGuard() {
  const isAdmin = useAuthStore((s) => s.user?.role === "admin");
  if (!isAdmin) return <Navigate to="/" replace />;
  return <Outlet />;
}
