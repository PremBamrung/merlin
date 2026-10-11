import { lazy, Suspense } from "react";
import { createBrowserRouter } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { ReaderSkeleton } from "@/components/common/Skeletons";
import LibraryRoute from "@/routes/library";
import ReaderRoute from "@/routes/reader";
import FeedRoute from "@/routes/feed";
import HomeRoute from "@/routes/home";

// Insights pulls in Recharts — lazy-load it so it stays out of the main bundle.
const InsightsRoute = lazy(() => import("@/routes/insights"));
// Chat pulls in the Vercel AI SDK — lazy-load so it stays in its own chunk.
const ChatRoute = lazy(() => import("@/routes/chat"));
const TopicsRoute = lazy(() => import("@/routes/topics"));
const TopicDetailRoute = lazy(() =>
  import("@/routes/topics").then((m) => ({ default: m.TopicDetailRoute })),
);
const TopicProposalsRoute = lazy(() =>
  import("@/routes/topics").then((m) => ({ default: m.TopicProposalsRoute })),
);
const TopicManageRoute = lazy(() =>
  import("@/routes/topics").then((m) => ({ default: m.TopicManageRoute })),
);

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      // The chat-first home: greeting, composer, what's new since last time.
      // It belongs to the Chat place (the rail marks Chat as current here).
      { index: true, element: <HomeRoute /> },
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
        path: "topics/proposals",
        element: (
          <Suspense fallback={<ReaderSkeleton />}>
            <TopicProposalsRoute />
          </Suspense>
        ),
      },
      {
        path: "topics/manage",
        element: (
          <Suspense fallback={<ReaderSkeleton />}>
            <TopicManageRoute />
          </Suspense>
        ),
      },
      {
        path: "topics/:slug",
        element: (
          <Suspense fallback={<ReaderSkeleton />}>
            <TopicDetailRoute />
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
