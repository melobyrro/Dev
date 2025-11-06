import { useQuery } from '@tanstack/react-query';
import { videoService } from '../services/videoService';

export function useVideoDetail(videoId: string) {
  return useQuery({
    queryKey: ['video', videoId],
    queryFn: () => videoService.fetchVideoDetail(videoId),
    enabled: !!videoId, // Only fetch if videoId exists
  });
}
