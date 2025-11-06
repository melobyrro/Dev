import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Layout from './components/Layout';

// Create a QueryClient instance
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 5 * 60 * 1000, // 5 minutes
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<div className="p-8"><h1>Home - Coming Soon</h1></div>} />
            <Route path="/channels" element={<div className="p-8"><h1>Channels - Coming Soon</h1></div>} />
            <Route path="/videos/:channelId" element={<div className="p-8"><h1>Videos - Coming Soon</h1></div>} />
            <Route path="/video/:videoId" element={<div className="p-8"><h1>Video Detail - Coming Soon</h1></div>} />
            <Route path="/chatbot" element={<div className="p-8"><h1>Chatbot - Coming Soon</h1></div>} />
            <Route path="*" element={<div className="p-8"><h1>404 - Page Not Found</h1></div>} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
