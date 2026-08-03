import { lazy, Suspense } from "react";
import { createBrowserRouter, Navigate } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { ReaderSkeleton } from "@/components/common/Skeletons";
import LibraryRoute from "@/routes/library";
import ReaderRoute from "@/routes/reader";
import FeedRoute from "@/routes/feed";

// Insights pulls in Recharts — lazy-load it so it stays out of the main bundle.
const InsightsRoute = lazy(() => import("@/routes/insights"));
// Chat pulls in the Vercel AI SDK — lazy-load so it stays in its own chunk.
const ChatRoute = lazy(() => import("@/routes/chat"));
const TopicsRoute = lazy(() => import("@/routes/topics"));

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      // Library *is* the home page. It redirects rather than rendering here so
      // there's one canonical URL: the route keeps all its filter/sort/page
      // state in the query string, and a second path rendering it would split
      // bookmarks and leave the top-bar nav with nothing marked active.
      // Reloading the redirect target is safe — api/main.py serves the SPA
      // shell for any extensionless path, not just `/`.
      { index: true, element: <Navigate to="/library" replace /> },
      { path: "feed", element: <FeedRoute /> },
      { path: "library", element: <LibraryRoute /> },
      { path: "library/:id", element: <ReaderRoute /> },
      {
        path: "topics",
        element: (
          <Suspense fallback={<ReaderSkeleton />}>
            <TopicsRoute />
          </Suspense>
        ),
      },
      {
        path: "chat",
        element: (
          <Suspense fallback={<ReaderSkeleton />}>
            <ChatRoute />
          </Suspense>
        ),
      },
      {
        path: "insights",
        element: (
          <Suspense fallback={<ReaderSkeleton />}>
            <InsightsRoute />
          </Suspense>
        ),
      },
    ],
  },
]);
