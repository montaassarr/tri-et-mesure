import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { ApiError } from "./api/client";
import { router } from "./router";
import "./index.css";

// Brand theme: AXA-inspired by default; VITE_BRAND=neutral gives an unbranded build.
document.documentElement.dataset.brand = import.meta.env.VITE_BRAND ?? "axa";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Do not retry auth or permission errors: they will not fix themselves.
      retry: (count, error) =>
        count < 1 && !(error instanceof ApiError && [401, 403, 404].includes(error.status)),
      refetchOnWindowFocus: false,
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
);
