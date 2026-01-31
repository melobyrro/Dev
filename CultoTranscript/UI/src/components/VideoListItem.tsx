import type { VideoDTO, VideoStatus } from '../types';
import StatusChip from './StatusChip';
import { formatDuration, formatDate, formatVideoTitle } from '../lib/utils';
import { useVideoStore } from '../stores/videoStore';

interface VideoListItemProps {
  video: VideoDTO;
}

export function VideoListItem({ video }: VideoListItemProps) {
  const { setSelectedVideoId } = useVideoStore();

  return (
    <div
      data-testid="video-card"
      data-video-id={video.id}
      onClick={() => setSelectedVideoId(video.id)}
      className="bg-white dark:bg-gray-800 rounded-lg p-4 shadow-sm hover:shadow-md transition-shadow cursor-pointer"
    >
      <div className="flex gap-4">
        {video.thumbnail_url && (
          <img
            data-testid="video-thumbnail"
            src={video.thumbnail_url}
            alt={video.title}
            className="w-32 h-20 object-cover rounded"
          />
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <h3
              data-testid="video-title"
              className="font-semibold text-gray-900 dark:text-white text-sm line-clamp-2"
            >
              {formatVideoTitle(video)}
            </h3>
            {video.status !== VideoStatus.PROCESSED && <StatusChip status={video.status} />}
          </div>
          <div
            data-testid="video-date"
            className="flex items-center gap-4 mt-2 text-sm text-gray-600 dark:text-gray-400"
          >
            <span>{formatDuration(video.duration)}</span>
            <span>{formatDate(video.published_at || video.created_at)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
