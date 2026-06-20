import { lazy, Suspense } from "react";
import { createBrowserRouter } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { ReaderSkeleton } from "@/components/common/Skeletons";
import TodayRoute from "@/routes/today";
import LibraryRoute from "@/routes/library";
import ReaderRoute from "@/routes/reader";
import FeedRoute from "@/routes/feed";

// Insights pulls in Recharts — lazy-load it so it stays out of the main bundle.
const InsightsRoute = lazy(() => import("@/routes/insights"));
// Chat pulls in the Vercel AI SDK — lazy-load so it stays in its own chunk.
const ChatRoute = lazy(() => import("@/routes/chat"));

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <TodayRoute /> },
      { path: "feed", element: <FeedRoute /> },
      { path: "library", element: <LibraryRoute /> },
      { path: "library/:id", element: <ReaderRoute /> },
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
