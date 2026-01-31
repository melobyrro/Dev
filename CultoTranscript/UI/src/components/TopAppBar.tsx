import { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useVideoStore } from '../stores/videoStore';

interface TopAppBarProps {
  onThemeToggle?: () => void;
  currentTheme?: 'light' | 'dark';
}

export default function TopAppBar({ onThemeToggle, currentTheme = 'light' }: TopAppBarProps) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const location = useLocation();
  const { channels, selectedChannelId, setSelectedChannelId } = useVideoStore();

  // Close user menu when clicking outside
  useEffect(() => {
    const handleClickOutside = () => {
      if (userMenuOpen) {
        setUserMenuOpen(false);
      }
    };
    document.addEventListener('click', handleClickOutside);
    return () => document.removeEventListener('click', handleClickOutside);
  }, [userMenuOpen]);

  const handleChannelChange = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    await setSelectedChannelId(e.target.value);
  };

  const handleLogout = () => {
    window.location.href = '/logout';
  };

  const navLinks = [
    { path: '/', label: 'Sermões', testId: 'nav-videos' },
    { path: '/reports', label: 'Relatórios', testId: 'nav-reports' },
    { path: '/admin', label: 'Admin', testId: 'nav-admin' },
    { path: '/database', label: 'Sermões DB', testId: 'nav-database' },
  ];

  const isActiveRoute = (path: string) => {
    if (path === '/') {
      return location.pathname === '/' || location.pathname === '/channels';
    }
    return location.pathname === path || location.pathname.startsWith(path + '/');
  };

  return (
    <header className="fixed top-0 left-0 right-0 z-50 backdrop-blur-md bg-white/80 dark:bg-gray-900/80 border-b border-gray-200 dark:border-gray-700">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <div className="flex-shrink-0">
            <Link to="/" data-testid="nav-home" className="flex items-center">
              <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent" style={{ fontFamily: 'Fraunces, serif' }}>
                CultoTranscript
              </h1>
            </Link>
          </div>

          {/* Channel Selector */}
          {channels.length >= 1 && (
            <div className="hidden md:flex items-center ml-6">
              <select
                value={selectedChannelId || ''}
                onChange={handleChannelChange}
                className="text-sm bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-500 rounded-lg px-3 py-1.5 text-gray-900 dark:text-white font-medium focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer"
                aria-label="Selecionar igreja"
              >
                {channels.map((channel) => (
                  <option key={channel.id} value={String(channel.id)}>
                    {channel.title}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Desktop Navigation */}
          <nav className="hidden md:flex items-center space-x-8">
            {navLinks.map((link) => (
              <Link
                key={link.path}
                to={link.path}
                data-testid={link.testId}
                className={`text-sm font-medium transition-colors duration-200 ${
                  isActiveRoute(link.path)
                    ? 'text-blue-600 dark:text-blue-400 border-b-2 border-blue-600 dark:border-blue-400 pb-1'
                    : 'text-gray-700 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400'
                }`}
              >
                {link.label}
              </Link>
            ))}
          </nav>

          {/* Right side: Theme Toggle + User Menu */}
          <div className="hidden md:flex items-center space-x-4">
            {/* Theme Toggle Button */}
            <button
              data-testid="theme-toggle"
              onClick={onThemeToggle}
              className="p-2 rounded-lg bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors duration-200"
              aria-label="Toggle theme"
            >
              {currentTheme === 'light' ? (
                <svg className="w-5 h-5 text-gray-700 dark:text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
                </svg>
              ) : (
                <svg className="w-5 h-5 text-gray-700 dark:text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
                </svg>
              )}
            </button>

            {/* User Menu with Dropdown */}
            <div className="relative">
              <button
                onClick={(e) => { e.stopPropagation(); setUserMenuOpen(!userMenuOpen); }}
                className="p-2 rounded-lg bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors duration-200"
                aria-label="User menu"
              >
                <svg className="w-5 h-5 text-gray-700 dark:text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
              </button>

              {userMenuOpen && (
                <div className="absolute right-0 mt-2 w-48 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 py-1 z-50">
                  <Link
                    to="/settings"
                    onClick={() => setUserMenuOpen(false)}
                    className="block px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700"
                  >
                    Configurações
                  </Link>
                  <button
                    onClick={handleLogout}
                    className="w-full text-left px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700"
                  >
                    Sair
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Mobile Menu Button */}
          <div className="md:hidden">
            <button
              data-testid="mobile-menu-button"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-2 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
              aria-label="Toggle menu"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                {mobileMenuOpen ? (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                ) : (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                )}
              </svg>
            </button>
          </div>
        </div>

        {/* Mobile Menu */}
        {mobileMenuOpen && (
          <div className="md:hidden py-4 border-t border-gray-200 dark:border-gray-700">
            <nav className="flex flex-col space-y-4">
              {navLinks.map((link) => (
                <Link
                  key={link.path}
                  to={link.path}
                  data-testid={link.testId}
                  onClick={() => setMobileMenuOpen(false)}
                  className={`text-sm font-medium px-2 py-1 rounded ${
                    isActiveRoute(link.path)
                      ? 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20'
                      : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800'
                  }`}
                >
                  {link.label}
                </Link>
              ))}
              {/* Mobile Channel Selector */}
              {channels.length >= 1 && (
                <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
                  <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">
                    Igreja
                  </label>
                  <select
                    value={selectedChannelId || ''}
                    onChange={handleChannelChange}
                    className="w-full text-sm bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-500 rounded-lg px-3 py-2 text-gray-900 dark:text-white font-medium"
                  >
                    {channels.map((channel) => (
                      <option key={channel.id} value={String(channel.id)}>
                        {channel.title}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              <div className="flex flex-col space-y-2 pt-4 border-t border-gray-200 dark:border-gray-700">
                <Link
                  to="/settings"
                  onClick={() => setMobileMenuOpen(false)}
                  className="px-2 py-1 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded"
                >
                  Configurações
                </Link>
                <div className="flex items-center justify-between">
                  <button
                    data-testid="theme-toggle"
                    onClick={onThemeToggle}
                    className="flex items-center space-x-2 px-2 py-1 text-sm text-gray-700 dark:text-gray-300"
                  >
                    <span>Tema</span>
                    {currentTheme === 'light' ? '🌙' : '☀️'}
                  </button>
                  <button
                    onClick={handleLogout}
                    className="px-4 py-1 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded"
                  >
                    Sair
                  </button>
                </div>
              </div>
            </nav>
          </div>
        )}
      </div>
    </header>
  );
}
