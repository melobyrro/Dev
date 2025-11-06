/**
 * Test file to verify DTO imports work correctly
 * DELETE THIS FILE after verification
 */

import type { VideoDTO, ChannelDTO } from './index';
import { VideoStatus, EventType } from './index';

// Test that types are properly imported
export const testVideo: VideoDTO = {
  id: '1',
  title: 'Test Video',
  youtube_id: 'abc123',
  status: VideoStatus.PENDING,
  duration: 3600,
  created_at: new Date().toISOString(),
  channel_id: 'channel1',
};

export const testChannel: ChannelDTO = {
  id: 'channel1',
  title: 'Test Channel',
  youtube_channel_id: 'UCxxx',
  created_at: new Date().toISOString(),
  total_videos: 10,
  processed_videos: 5,
};

// Verify enums work
export const testEventType = EventType.HEARTBEAT;
export const testStatus = VideoStatus.PROCESSED;
