import { Outlet, Link } from 'react-router-dom';

export default function Layout() {
  return (
    <div className="min-h-screen flex flex-col bg-background">
      {/* Header */}
      <header className="bg-surface border-b border-border shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center">
              <h1 className="text-2xl font-bold text-primary">CultoTranscript</h1>
            </div>
            <nav className="flex gap-4">
              <Link
                to="/"
                className="px-3 py-2 rounded-md text-sm font-medium text-text hover:bg-border transition-colors"
              >
                Home
              </Link>
              <Link
                to="/channels"
                className="px-3 py-2 rounded-md text-sm font-medium text-text hover:bg-border transition-colors"
              >
                Channels
              </Link>
              <Link
                to="/chatbot"
                className="px-3 py-2 rounded-md text-sm font-medium text-text hover:bg-border transition-colors"
              >
                Chatbot
              </Link>
            </nav>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="bg-surface border-t border-border py-4">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center text-sm text-text-muted">
          CultoTranscript v2.0 - Automated Sermon Transcription
        </div>
      </footer>
    </div>
  );
}
