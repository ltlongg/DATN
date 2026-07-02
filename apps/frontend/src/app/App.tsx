import { useEffect } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { getMe } from "@/api/auth";
import { useAuthStore } from "@/store/authStore";
import { routes } from "@/app/routes";

const router = createBrowserRouter(routes);

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 30_000 },
  },
});

/** Có token từ localStorage -> xác thực lại 1 lần khi mở app (token cũ/bị khóa -> client
 * đã clear ở 401). Chạy 1 lần lúc mount. */
function useBootAuth() {
  useEffect(() => {
    if (!useAuthStore.getState().token) return;
    getMe()
      .then((user) => useAuthStore.getState().setUser(user))
      .catch(() => {
        /* 401 đã clear trong client; lỗi mạng khác thì giữ token, thử lại lần sau */
      });
  }, []);
}

export default function App() {
  useBootAuth();
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}
