import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import TodayPage from '@/pages/TodayPage'
import DigestPage from '@/pages/DigestPage'
import InboxPage from '@/pages/InboxPage'
import LibraryPage from '@/pages/LibraryPage'
import ChatPage from '@/pages/ChatPage'
import GraphPage from '@/pages/GraphPage'
import YouTubePage from '@/pages/YouTubePage'
import RedditPage from '@/pages/RedditPage'
import IngestReviewPage from '@/pages/IngestReviewPage'
import SharePage from '@/pages/SharePage'
import LibraryItemPage from '@/pages/LibraryItemPage'

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 2, staleTime: 30000 } },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Navigate to="/today" replace />} />
          <Route path="/today" element={<TodayPage />} />
          <Route path="/digest" element={<DigestPage />} />
          <Route path="/inbox" element={<InboxPage />} />
          <Route path="/library" element={<LibraryPage />} />
          <Route path="/library/:id" element={<LibraryItemPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/graph" element={<GraphPage />} />
          <Route path="/youtube" element={<YouTubePage />} />
          <Route path="/reddit" element={<RedditPage />} />
          <Route path="/inbox/review/:id" element={<IngestReviewPage />} />
          <Route path="/share" element={<SharePage />} />
          <Route path="*" element={<Navigate to="/today" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
