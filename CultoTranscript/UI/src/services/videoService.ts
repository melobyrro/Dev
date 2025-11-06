import axios from 'axios';
import { config } from '../lib/config';
import type {
  VideoDTO,
  VideoDetailDTO,
  ApiResponse,
  VideoStatus,
} from '../types';

const api = axios.create({
  baseURL: config.apiBaseUrl,
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface VideoFilters {
  channel_id?: string;
  status?: VideoStatus;
  search?: string;
  limit?: number;
  offset?: number;
}

interface VideosResponse {
  videos: VideoDTO[];
  total: number;
}

class VideoService {
  async fetchVideos(filters?: VideoFilters): Promise<VideoDTO[]> {
    const params = new URLSearchParams();
    
    if (filters?.channel_id) params.append('channel_id', filters.channel_id);
    if (filters?.status) params.append('status', filters.status);
    if (filters?.search) params.append('search', filters.search);
    if (filters?.limit) params.append('limit', String(filters.limit));
    if (filters?.offset) params.append('offset', String(filters.offset));

    const url = '/api/v2/videos/?' + params.toString();
    const response = await api.get<ApiResponse<VideosResponse>>(url);
    
    if (response.data.success) {
      return response.data.data.videos; // Extract videos array from nested object
    }
    
    throw new Error(response.data.detail || 'Failed to fetch videos');
  }

  async fetchVideoDetail(videoId: string): Promise<VideoDetailDTO> {
    const url = '/api/v2/videos/' + videoId;
    const response = await api.get<ApiResponse<VideoDetailDTO>>(url);
    
    if (response.data.success) {
      return response.data.data;
    }
    
    throw new Error(response.data.detail || 'Failed to fetch video details');
  }

  async reprocessVideo(videoId: string): Promise<void> {
    const url = '/api/v2/videos/' + videoId + '/reprocess';
    const response = await api.post<ApiResponse>(url);
    
    if (!response.data.success) {
      throw new Error(response.data.detail || 'Failed to reprocess video');
    }
  }

  async deleteVideo(videoId: string): Promise<void> {
    const url = '/api/v2/videos/' + videoId;
    const response = await api.delete<ApiResponse>(url);
    
    if (!response.data.success) {
      throw new Error(response.data.detail || 'Failed to delete video');
    }
  }

  async updateTranscript(videoId: string, transcript: string): Promise<void> {
    const url = '/api/v2/videos/' + videoId + '/transcript';
    const response = await api.patch<ApiResponse>(url, { transcript });
    
    if (!response.data.success) {
      throw new Error(response.data.detail || 'Failed to update transcript');
    }
  }
}

export const videoService = new VideoService();
