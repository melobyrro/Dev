import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { sseClient } from '../lib/sseClient';
import { useVideoStore } from '../stores/videoStore';
import { useJobStore } from '../stores/jobStore';
import { EventType, VideoStatus } from '../types';
import type { VideoStatusEventDTO, SummaryReadyEventDTO, ErrorEventDTO } from '../types';
import toast from 'react-hot-toast';

function mapVideoStatusToJobStatus(status: VideoStatus): 'queued' | 'processing' | 'completed' | 'failed' {
    switch (status) {
        case VideoStatus.PENDING:
        case VideoStatus.QUEUED:
            return 'queued';
        case VideoStatus.PROCESSING:
            return 'processing';
        case VideoStatus.PROCESSED:
            return 'completed';
        case VideoStatus.FAILED:
            return 'failed';
        default:
            return 'processing';
    }
}

export function useSSE() {
  const queryClient = useQueryClient();
  const updateVideoStatus = useVideoStore((state) => state.updateVideoStatus);
  const updateJobByVideoId = useJobStore((state) => state.updateJobByVideoId);

  useEffect(() => {
    sseClient.connect();

    const handleVideoStatus = (event: VideoStatusEventDTO) => {
      updateVideoStatus(event.video_id, event.status);

      // Update job progress from SSE event
      updateJobByVideoId(event.video_id, {
          progress: event.progress || 0,
          message: event.message,
          status: mapVideoStatusToJobStatus(event.status as VideoStatus),
      });

      queryClient.invalidateQueries({ queryKey: ['video', event.video_id] });
      queryClient.invalidateQueries({ queryKey: ['videos'] });

      if (event.status === 'PROCESSED') {
        toast.success('Vídeo processado com sucesso!');
      } else if (event.status === 'FAILED') {
        toast.error('Falha ao processar vídeo: ' + (event.message || 'Erro desconhecido'));
      }
    };

    const handleSummaryReady = (event: SummaryReadyEventDTO) => {
      queryClient.invalidateQueries({ queryKey: ['video', event.video_id] });
      toast.success('Análise do vídeo concluída!');
    };

    const handleError = (event: ErrorEventDTO) => {
      toast.error(event.error_message);
    };

    sseClient.on(EventType.VIDEO_STATUS, handleVideoStatus);
    sseClient.on(EventType.SUMMARY_READY, handleSummaryReady);
    sseClient.on(EventType.ERROR, handleError);

    return () => {
      sseClient.off(EventType.VIDEO_STATUS, handleVideoStatus);
      sseClient.off(EventType.SUMMARY_READY, handleSummaryReady);
      sseClient.off(EventType.ERROR, handleError);
      sseClient.disconnect();
    };
  }, [queryClient, updateVideoStatus, updateJobByVideoId]);
}
