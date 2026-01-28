import { create } from 'zustand';
import { config } from '../lib/config';

export interface UserInfo {
  id: number;
  email: string;
  is_superadmin: boolean;
  last_login: string | null;
}

export interface ChurchInfo {
  id: number;
  title: string;
  role: string;
  subdomain: string;
  youtube_url: string;
}

interface AuthState {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: UserInfo | null;
  role: string | null;
  currentChannelId: number | null;
  churches: ChurchInfo[];
  error: string | null;

  // Actions
  checkAuth: () => Promise<void>;
  logout: () => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  isAuthenticated: false,
  isLoading: true,
  user: null,
  role: null,
  currentChannelId: null,
  churches: [],
  error: null,

  checkAuth: async () => {
    set({ isLoading: true, error: null });
    try {
      const response = await fetch(`${config.apiBaseUrl}/api/me`, {
        credentials: 'include',
      });

      if (!response.ok) {
        throw new Error('Failed to check authentication');
      }

      const data = await response.json();

      set({
        isAuthenticated: data.authenticated,
        user: data.user,
        role: data.role,
        currentChannelId: data.current_channel_id,
        churches: data.churches || [],
        isLoading: false,
      });
    } catch (error) {
      console.error('Auth check failed:', error);
      set({
        isAuthenticated: false,
        user: null,
        role: null,
        currentChannelId: null,
        churches: [],
        isLoading: false,
        error: error instanceof Error ? error.message : 'Authentication check failed',
      });
    }
  },

  logout: async () => {
    try {
      await fetch(`${config.apiBaseUrl}/logout`, {
        credentials: 'include',
      });
    } catch (error) {
      console.error('Logout failed:', error);
    }

    set({
      isAuthenticated: false,
      user: null,
      role: null,
      currentChannelId: null,
      churches: [],
    });
  },

  clearError: () => set({ error: null }),
}));
