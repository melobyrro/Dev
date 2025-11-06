import { useState } from 'react';
import type { MonthlyGroupDTO } from '../types';
import { VideoListItem } from './VideoListItem';
import { formatDuration } from '../lib/utils';

interface MonthlyGroupProps {
  group: MonthlyGroupDTO;
}

export function MonthlyGroup({ group }: MonthlyGroupProps) {
  const [isExpanded, setIsExpanded] = useState(true);

  return (
    <div data-testid="monthly-group" className="mb-6">
      <button
        data-testid="group-header"
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-4 bg-white dark:bg-gray-800 rounded-lg shadow-sm hover:shadow-md transition-shadow"
      >
        <div className="flex items-center gap-3">
          <svg
            className={'w-5 h-5 transition-transform ' + (isExpanded ? 'rotate-90' : '')}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
            {group.month_label}
          </h2>
        </div>
        <div className="flex items-center gap-4 text-sm text-gray-600 dark:text-gray-400">
          <span>{group.videos.length} vídeos</span>
          <span>{formatDuration(group.total_duration)}</span>
        </div>
      </button>

      {isExpanded && (
        <div className="mt-4 space-y-4">
          {group.videos.map((video) => (
            <VideoListItem key={video.id} video={video} />
          ))}
        </div>
      )}
    </div>
  );
}
