import { Outlet } from "react-router-dom";
import { AppSidebar } from "@/components/AppSidebar";

/** Shell chung sau đăng nhập: sidebar điều hướng dọc trái + vùng nội dung. Page con dùng
 * h-full (AppShell giữ h-screen). */
export default function AppShell() {
  return (
    <div className="flex h-screen overflow-hidden">
      <AppSidebar />
      <div className="flex-1 overflow-hidden">
        <Outlet />
      </div>
    </div>
  );
}
