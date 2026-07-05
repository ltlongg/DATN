import { Suspense } from "react";
import { Outlet } from "react-router-dom";
import { Spinner } from "@/components/Spinner";

/** Vùng nội dung khu quản trị: chỉ còn padding + Suspense cho child routes (một số lazy:
 * kb/graph, cost). Nav đã chuyển sang AppSidebar. */
export default function AdminLayout() {
  return (
    <main className="h-full overflow-y-auto p-6">
      <Suspense fallback={<Spinner />}>
        <Outlet />
      </Suspense>
    </main>
  );
}
