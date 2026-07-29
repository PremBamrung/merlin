import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router-dom";
import { router } from "./router";
import { Toaster } from "./components/ui/toaster";
// Self-hosted fonts (no Google CDN): Inter variable for all prose and controls,
// JetBrains Mono 400/500 for the mono eyebrows/metadata, and Archivo variable as
// the display face for titles and headings. Bundled by Vite → no privacy leak,
// no FOUT, and the offline NAS deploy keeps its type.
import "@fontsource-variable/inter";
import "@fontsource/jetbrains-mono/400.css";
import "@fontsource/jetbrains-mono/500.css";
import "@fontsource-variable/archivo";
import "./styles/index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Five minutes, not thirty seconds. This is a personal knowledge base:
      // nothing changes behind your back except your own ingests, and those
      // invalidate the keys they touch explicitly. The old 30s meant that coming
      // back to the Library after half a minute refetched — and flashed a
      // skeleton over data that was already in the cache.
      // (Chat's own queries set their own staleTime and are unaffected.)
      staleTime: 5 * 60_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
      <Toaster />
    </QueryClientProvider>
  </StrictMode>,
);
