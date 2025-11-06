// Use relative URLs in production (when served from same domain)
// Use absolute URL in development (when React dev server is separate from API)
const isProduction = import.meta.env.PROD;
export const API_BASE_URL = isProduction 
  ? '' // Empty string = relative URLs to same domain
  : (import.meta.env.VITE_API_BASE_URL || 'http://192.168.1.11:8000');

export const DEFAULT_CHANNEL_ID = '1';

export const config = {
  apiBaseUrl: API_BASE_URL,
  defaultChannelId: DEFAULT_CHANNEL_ID,
  sseUrl: `${API_BASE_URL}/api/v2/events/stream`,
};
