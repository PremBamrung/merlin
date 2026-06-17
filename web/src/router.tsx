import { lazy, Suspense } from "react";
import { createBrowserRouter } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { ReaderSkeleton } from "@/components/common/Skeletons";
import TodayRoute from "@/routes/today";
import LibraryRoute from "@/routes/library";
import ReaderRoute from "@/routes/reader";
import ChatRoute from "@/routes/chat";
import FeedRoute from "@/routes/feed";

// Insights pulls in Recharts — lazy-load it so it stays out of the main bundle.
const InsightsRoute = lazy(() => import("@/routes/insights"));

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <TodayRoute /> },
      { path: "feed", element: <FeedRoute /> },
      { path: "library", element: <LibraryRoute /> },
      { path: "library/:id", element: <ReaderRoute /> },
      { path: "chat", element: <ChatRoute /> },
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
