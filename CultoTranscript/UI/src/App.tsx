import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Layout from './components/Layout';
import { VideoList } from './components/VideoList';
import Login from './pages/Login';
import Register from './pages/Register';
import Admin from './pages/Admin';
import Settings from './pages/Settings';
import Database from './pages/Database';
import { ProtectedRoute } from './components/ProtectedRoute';
import { useAuthStore } from './stores/authStore';
import { useVideoStore } from './stores/videoStore';
import { useEffect } from 'react';
import Reports from './pages/Reports';
import { AIDrawer } from './components/AIDrawer';
import { FloatingActionButton } from './components/FloatingActionButton';
import { ProgressModal } from './components/ProgressModal';

function LegacyVideosRedirect() {
  useEffect(() => {
    window.location.href = '/videos';
  }, []);
  return null;
}

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

function AppContent() {
  const { checkAuth } = useAuthStore();
  const { fetchChannels } = useVideoStore();

  // Check authentication status on app initialization
  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  // Fetch channels on app startup
  useEffect(() => {
    fetchChannels();
  }, [fetchChannels]);

  return (
    <>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route index element={<VideoList />} />
          <Route path="/channels" element={<VideoList />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/videos" element={<LegacyVideosRedirect />} />
          <Route
            path="/database"
            element={
              <ProtectedRoute requireSuperadmin>
                <Database />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin"
            element={
              <ProtectedRoute requiredRole="admin">
                <Admin />
              </ProtectedRoute>
            }
          />
          <Route
            path="/settings"
            element={
              <ProtectedRoute>
                <Settings />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<div className="p-8 text-center"><h1>404 - Página não encontrada</h1></div>} />
        </Route>
      </Routes>

      {/* Global components */}
      <AIDrawer />
      <FloatingActionButton />
      <ProgressModal />
    </>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppContent />
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
