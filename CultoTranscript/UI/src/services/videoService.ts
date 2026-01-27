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

export interface JobStatusResponse {
  job_id: number;
  status: string;
  progress?: string;
  error?: string;
  metadata?: Record<string, unknown>;
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

  async reprocessVideo(videoId: string, password: string): Promise<{ job_id: number }> {
    const url = '/api/videos/' + videoId + '/reprocess';
    const response = await api.post<ApiResponse<{ job_id: number }>>(url, { password });

    if (!response.data.success) {
      throw new Error(response.data.detail || 'Failed to reprocess video');
    }
    return response.data.data;
  }

  async deleteVideo(videoId: string, password: string): Promise<void> {
    const url = '/api/videos/' + videoId;
    const response = await api.delete<ApiResponse>(url, { data: { password } });

    if (!response.data.success) {
      throw new Error(response.data.detail || 'Failed to delete video');
    }
  }

  async getJobStatus(jobId: number): Promise<JobStatusResponse> {
    const url = '/api/jobs/' + jobId + '/status';
    const response = await api.get<JobStatusResponse>(url);
    return response.data;
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
