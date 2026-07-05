import { lazy } from "react";
import { type RouteObject, Navigate } from "react-router-dom";
import AppShell from "@/components/AppShell";
import { RequireAuth } from "@/features/auth/RequireAuth";
import { RoleGuard } from "@/features/auth/RoleGuard";
import LoginPage from "@/pages/LoginPage";
import AskPage from "@/pages/AskPage";
import AdminLayout from "@/pages/AdminLayout";
import AdminDocumentsPage from "@/pages/AdminDocumentsPage";
import AdminKbChunksPage from "@/pages/AdminKbChunksPage";
import AdminKbTimelinePage from "@/pages/AdminKbTimelinePage";
import AdminLogsPage from "@/pages/AdminLogsPage";
import AdminUsersPage from "@/pages/AdminUsersPage";
import AdminConfigPage from "@/pages/AdminConfigPage";

// Lazy: chỉ các trang nặng (graph = react-force-graph-2d, cost = recharts) — tách khỏi bundle
// chính. Các trang admin còn lại nhẹ nên import thẳng.
const AdminKbGraphPage = lazy(() => import("@/pages/AdminKbGraphPage"));
const AdminCostPage = lazy(() => import("@/pages/AdminCostPage"));
const AdminPromptsPage = lazy(() => import("@/pages/AdminPromptsPage"));

/**
 * Route cứng: `/` khu user (mọi role), `/admin/*` chỉ admin (RoleGuard). Mỗi chức năng admin
 * là 1 route con riêng (nav dọc ở AppSidebar), không còn tab ngang gộp. Redirect back-compat
 * cho path gộp cũ (`/admin/kb`, `/admin/advanced`). Export array để test bằng memory router.
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
                  { index: true, element: <Navigate to="/admin/logs" replace /> },
                  { path: "documents", element: <AdminDocumentsPage /> },
                  // KB Inspector — mỗi mục 1 route con độc lập (bỏ điều hướng chéo)
                  { path: "kb", element: <Navigate to="/admin/kb/chunks" replace /> },
                  { path: "kb/chunks", element: <AdminKbChunksPage /> },
                  { path: "kb/graph", element: <AdminKbGraphPage /> },
                  { path: "kb/timeline", element: <AdminKbTimelinePage /> },
                  // Quản trị
                  { path: "logs", element: <AdminLogsPage /> },
                  { path: "users", element: <AdminUsersPage /> },
                  { path: "cost", element: <AdminCostPage /> },
                  { path: "prompts", element: <AdminPromptsPage /> },
                  { path: "config", element: <AdminConfigPage /> },
                  // Back-compat: route gộp cũ -> mục đầu nhóm tương ứng
                  { path: "advanced", element: <Navigate to="/admin/logs" replace /> },
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
