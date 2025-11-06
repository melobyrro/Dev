import { useQuery } from '@tanstack/react-query';
import { videoService, type VideoFilters } from '../services/videoService';

export function useVideos(filters?: VideoFilters) {
  return useQuery({
    queryKey: ['videos', filters],
    queryFn: () => videoService.fetchVideos(filters),
    staleTime: 2 * 60 * 1000, // 2 minutes
  });
}
