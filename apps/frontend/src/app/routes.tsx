import { lazy } from "react";
import { type RouteObject, Navigate } from "react-router-dom";
import AppShell from "@/components/AppShell";
import { RequireAuth } from "@/features/auth/RequireAuth";
import { RoleGuard } from "@/features/auth/RoleGuard";
import LoginPage from "@/pages/LoginPage";
import AskPage from "@/pages/AskPage";
import AdminLayout from "@/pages/AdminLayout";
import AdminDocumentsPage from "@/pages/AdminDocumentsPage";

// Lazy: 2 trang admin nặng (KB dùng react-force-graph-2d, Advanced dùng recharts) -> tách
// khỏi bundle chính, người dùng thường không tải.
const AdminKbPage = lazy(() => import("@/pages/AdminKbPage"));
const AdminAdvancedPage = lazy(() => import("@/pages/AdminAdvancedPage"));

/**
 * Route cứng: `/` khu user (mọi role), `/admin/*` chỉ admin (RoleGuard). Child routes admin
 * (documents/kb/advanced) thêm dần theo phase. Export dạng array để test bằng memory router.
 */
export const routes: RouteObject[] = [
  { path: "/login", element: <LoginPage /> },
  {
    path: "/",
    element: <RequireAuth />,
    children: [
      {
        element: <AppShell />,
        children: [
          { index: true, element: <AskPage /> },
          {
            path: "admin",
            element: <RoleGuard />,
            children: [
              {
                element: <AdminLayout />,
                children: [
                  { index: true, element: <Navigate to="/admin/documents" replace /> },
                  { path: "documents", element: <AdminDocumentsPage /> },
                  { path: "kb", element: <AdminKbPage /> },
                  { path: "advanced", element: <AdminAdvancedPage /> },
                ],
              },
            ],
          },
        ],
      },
    ],
  },
  { path: "*", element: <Navigate to="/" replace /> },
];
