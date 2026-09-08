import { lazy } from "react";
import { type RouteObject, Navigate } from "react-router-dom";
import AppShell from "@/components/AppShell";
import { RequireAuth } from "@/features/auth/RequireAuth";
import { RoleGuard } from "@/features/auth/RoleGuard";
import { DEFAULT_CAMPAIGN_SLUG } from "@/features/campaigns/registry";
import { DEFAULT_FIGURE_SLUG } from "@/features/figures/registry";
import LoginPage from "@/pages/LoginPage";
import RegisterPage from "@/pages/RegisterPage";
import AskPage from "@/pages/AskPage";
import FigurePage from "@/pages/FigurePage";
import CampaignPage from "@/pages/CampaignPage";
import TimelinePage from "@/pages/TimelinePage";
import AdminLayout from "@/pages/AdminLayout";
import AdminDocumentsPage from "@/pages/AdminDocumentsPage";
import AdminKbChunksPage from "@/pages/AdminKbChunksPage";
import AdminKbTimelinePage from "@/pages/AdminKbTimelinePage";
import AdminLogsPage from "@/pages/AdminLogsPage";
import AdminUsersPage from "@/pages/AdminUsersPage";
import AdminActivityPage from "@/pages/AdminActivityPage";
import AdminConfigPage from "@/pages/AdminConfigPage";

// Lazy: chỉ các trang nặng (graph = react-force-graph-2d, cost = recharts) — tách khỏi bundle
// chính. Các trang admin còn lại nhẹ nên import thẳng.
const AdminKbGraphPage = lazy(() => import("@/pages/AdminKbGraphPage"));
const AdminCostPage = lazy(() => import("@/pages/AdminCostPage"));
const AdminPromptsPage = lazy(() => import("@/pages/AdminPromptsPage"));

/**
 * Route cứng: `/login` + `/register` công khai, `/` khu user (mọi role), `/admin/*` chỉ
 * admin (RoleGuard). Mỗi chức năng admin
 * là 1 route con riêng (nav dọc ở AppSidebar), không còn tab ngang gộp. Redirect back-compat
 * cho path gộp cũ (`/admin/kb`, `/admin/advanced`). Export array để test bằng memory router.
 */
export const routes: RouteObject[] = [
  { path: "/login", element: <LoginPage /> },
  { path: "/register", element: <RegisterPage /> },
  {
    path: "/",
    element: <RequireAuth />,
    children: [
      // Hai trang chuyên đề nằm NGOÀI AppShell: chiếm trọn màn hình, không sidebar.
      // `/danh-nhan` và `/chien-dich` đưa thẳng vào mục duy nhất đang có.
      {
        path: "danh-nhan",
        element: <Navigate to={`/danh-nhan/${DEFAULT_FIGURE_SLUG}`} replace />,
      },
      { path: "danh-nhan/:slug", element: <FigurePage /> },
      {
        path: "chien-dich",
        element: <Navigate to={`/chien-dich/${DEFAULT_CAMPAIGN_SLUG}`} replace />,
      },
      { path: "chien-dich/:slug", element: <CampaignPage /> },
      {
        element: <AppShell />,
        children: [
          { index: true, element: <AskPage /> },
          { path: "timeline", element: <TimelinePage /> },
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
                  { path: "activity", element: <AdminActivityPage /> },
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
