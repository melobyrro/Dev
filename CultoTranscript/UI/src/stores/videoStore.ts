import { create } from 'zustand';
import type { VideoDTO, VideoStatus, ChannelDTO } from '../types';
import { channelService } from '../services/channelService';

interface VideoFilters {
  status?: VideoStatus;
  search?: string;
  speaker?: string;
  date_start?: string;
  date_end?: string;
  theme?: string;
  biblical_ref?: string;
}

interface VideoStore {
  videos: VideoDTO[];
  loading: boolean;
  error: string | null;
  filters: VideoFilters;

  // Channels
  channels: ChannelDTO[];
  selectedChannelId: string | null;

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

  // Channel actions
  fetchChannels: () => Promise<void>;
  setSelectedChannelId: (id: string | null) => void;
}

export const useVideoStore = create<VideoStore>((set) => ({
  videos: [],
  loading: false,
  error: null,
  filters: {},

  channels: [],
  selectedChannelId: null,

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

  fetchChannels: async () => {
    try {
      const { channels, current_channel_id } = await channelService.fetchChannels();
      set({ channels });
      set((state) => {
        const alreadySelected = state.selectedChannelId;
        const currentFromSession = current_channel_id ? current_channel_id.toString() : null;
        const fallback = channels.length > 0 ? channels[0].id.toString() : null;

        if (alreadySelected) {
          return {};
        }

        return {
          selectedChannelId: currentFromSession || fallback,
        };
      });

      // If backend session had no channel set, align it to the selected one
      const targetChannelId = (current_channel_id || (channels[0]?.id ?? null));
      if (!current_channel_id && targetChannelId) {
        channelService.switchChurch(targetChannelId.toString()).catch((error) => {
          console.error('Failed to sync church selection', error);
        });
      }
    } catch (error) {
      console.error('Error fetching channels:', error);
    }
  },

  setSelectedChannelId: (id) => set({ selectedChannelId: id }),
}));
