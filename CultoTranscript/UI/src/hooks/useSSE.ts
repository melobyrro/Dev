import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { sseClient } from '../lib/sseClient';
import { useVideoStore } from '../stores/videoStore';
import { EventType } from '../types';
import type { VideoStatusEventDTO, SummaryReadyEventDTO, ErrorEventDTO } from '../types';
import toast from 'react-hot-toast';

export function useSSE() {
  const queryClient = useQueryClient();
  const updateVideoStatus = useVideoStore((state) => state.updateVideoStatus);

  useEffect(() => {
    sseClient.connect();

    const handleVideoStatus = (event: VideoStatusEventDTO) => {
      updateVideoStatus(event.video_id, event.status);
      
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
  }, [queryClient, updateVideoStatus]);
}
