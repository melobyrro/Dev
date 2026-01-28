import { useQuery } from '@tanstack/react-query';
import { videoService, type VideoFilters } from '../services/videoService';

interface UseVideosOptions {
  enabled?: boolean;
}

export function useVideos(filters?: VideoFilters, options?: UseVideosOptions) {
  return useQuery({
    queryKey: ['videos', filters],
    queryFn: () => videoService.fetchVideos(filters),
    staleTime: 2 * 60 * 1000, // 2 minutes
    enabled: options?.enabled ?? true,
  });
}
