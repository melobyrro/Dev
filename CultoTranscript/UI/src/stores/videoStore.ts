import { create } from 'zustand';
import type { VideoDTO, VideoStatus } from '../types';

interface VideoFilters {
  status?: VideoStatus;
  search?: string;
}

interface VideoStore {
  videos: VideoDTO[];
  loading: boolean;
  error: string | null;
  filters: VideoFilters;

  // Video detail drawer
  selectedVideoId: string | null;

  setVideos: (videos: VideoDTO[]) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setFilter: (key: keyof VideoFilters, value: any) => void;
  updateVideoStatus: (videoId: string, status: VideoStatus) => void;
  removeVideo: (videoId: string) => void;
  clearFilters: () => void;
  setSelectedVideoId: (id: string | null) => void;
}

export const useVideoStore = create<VideoStore>((set) => ({
  videos: [],
  loading: false,
  error: null,
  filters: {},
  selectedVideoId: null,

  setVideos: (videos) => set({ videos }),

  setLoading: (loading) => set({ loading }),

  setError: (error) => set({ error }),

  setFilter: (key, value) =>
    set((state) => ({
      filters: { ...state.filters, [key]: value },
    })),

  updateVideoStatus: (videoId, status) =>
    set((state) => ({
      videos: state.videos.map((video) =>
        video.id === videoId ? { ...video, status } : video
      ),
    })),

  removeVideo: (videoId) =>
    set((state) => ({
      videos: state.videos.filter((video) => video.id !== videoId),
    })),

  clearFilters: () => set({ filters: {} }),

  setSelectedVideoId: (id) => set({ selectedVideoId: id }),
}));
