import axios from 'axios';
import { config } from '../lib/config';
import type { ApiResponse } from '../types';

interface SpeakerSuggestion {
  id: number;
  name: string;
  video_count: number;
}

interface SpeakersResponse {
  suggestions: SpeakerSuggestion[];
}

class SpeakerService {
  async autocomplete(channelId?: string, q?: string): Promise<SpeakerSuggestion[]> {
    const params = new URLSearchParams();
    if (channelId) params.append('channel_id', channelId);
    if (q) params.append('q', q);
    const url = `/api/v2/speakers/autocomplete?${params.toString()}`;
    const response = await axios.get<ApiResponse<SpeakersResponse>>(url, {
      baseURL: config.apiBaseUrl,
      withCredentials: true,
    });

    if (response.data.success && response.data.data) {
      return response.data.data.suggestions;
    }

    return [];
  }
}

export const speakerService = new SpeakerService();
