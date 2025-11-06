import type { VideoDTO, MonthlyGroupDTO } from '../types';

const PORTUGUESE_MONTHS = [
  'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
  'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
];

export function groupVideosByMonth(videos: VideoDTO[]): MonthlyGroupDTO[] {
  const groups = new Map<string, MonthlyGroupDTO>();

  videos.forEach((video) => {
    // Use published_at for grouping (upload date)
    const date = new Date(video.published_at || video.created_at);
    const year = date.getFullYear();
    const month = date.getMonth() + 1; // 0-indexed, so add 1
    const key = year + '-' + month;

    if (!groups.has(key)) {
      groups.set(key, {
        year,
        month,
        month_label: PORTUGUESE_MONTHS[month - 1] + ' ' + year,
        videos: [],
        total_duration: 0,
      });
    }

    const group = groups.get(key)!;
    group.videos.push(video);
    group.total_duration += video.duration;
  });

  // Sort by date descending (newest first)
  return Array.from(groups.values()).sort((a, b) => {
    if (a.year !== b.year) return b.year - a.year;
    return b.month - a.month;
  });
}

export function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;

  if (hours > 0) {
    return hours + 'h ' + minutes + 'm';
  }
  return minutes + 'm ' + secs + 's';
}

export function formatDate(dateString: string): string {
  const date = new Date(dateString);
  const day = String(date.getDate()).padStart(2, '0');
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const year = date.getFullYear();
  return day + '/' + month + '/' + year;
}

/**
 * Format video title with upload date prefix
 * Format: mm/dd/yyyy - Title
 * Uses published_at (YouTube upload date) for the prefix
 */
export function formatVideoTitle(video: VideoDTO): string {
  const date = new Date(video.published_at || video.created_at);
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const year = date.getFullYear();
  return month + '/' + day + '/' + year + ' - ' + video.title;
}
