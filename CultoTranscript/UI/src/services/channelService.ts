import axios from 'axios';
import { config } from '../lib/config';
import type { ChannelDTO, ApiResponse } from '../types';

const api = axios.create({
  baseURL: config.apiBaseUrl,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
});

export interface ChannelListResponse {
  channels: ChannelDTO[];
  current_channel_id?: number | null;
}

class ChannelService {
  async fetchChannels(): Promise<ChannelListResponse> {
    const url = '/api/v2/channels/';
    const response = await api.get<ApiResponse<ChannelListResponse>>(url);

    if (response.data.success && response.data.data) {
      return {
        channels: response.data.data.channels,
        current_channel_id: response.data.data.current_channel_id,
      };
    }

    throw new Error('Failed to fetch channels');
  }

  async switchChurch(churchId: string): Promise<void> {
    if (!churchId) return;
    const url = '/api/v2/channels/switch';
    const response = await api.post<ApiResponse>(url, { church_id: Number(churchId) });

    if (!response.data.success) {
      throw new Error(response.data.detail || 'Failed to switch church');
    }
  }
}

export const channelService = new ChannelService();
