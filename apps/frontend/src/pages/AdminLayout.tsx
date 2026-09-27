import { Suspense } from "react";
import { Outlet } from "react-router-dom";
import { Spinner } from "@/components/Spinner";

/** Vùng nội dung khu quản trị: khung cuộn + bề rộng tối đa + Suspense cho child routes (một
 * số lazy: kb/graph, cost, prompts). Nav nằm ở AppSidebar. */
export default function AdminLayout() {
  return (
    <main className="h-full overflow-y-auto">
      <div className="mx-auto max-w-7xl px-6 py-8 lg:px-8">
        <Suspense fallback={<Spinner />}>
          <Outlet />
        </Suspense>
      </div>
    </main>
  );
}
