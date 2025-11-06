import axios, { AxiosError } from 'axios';
import { config } from '../lib/config';
import type { ChatRequestDTO, ChatResponseDTO, ApiResponse } from '../types';

const api = axios.create({
  baseURL: config.apiBaseUrl,
  headers: {
    'Content-Type': 'application/json',
  },
});

class ChatService {
  async sendMessage(
    channelId: string,
    message: string,
    sessionId: string
  ): Promise<ChatResponseDTO> {
    const request: ChatRequestDTO = {
      message,
      session_id: sessionId,
      channel_id: channelId,
    };

    try {
      const url = '/api/v2/channels/' + channelId + '/chat';
      const response = await api.post<ApiResponse<ChatResponseDTO>>(url, request);

      if (response.data.success) {
        return response.data.data;
      }

      throw new Error(response.data.detail || 'Failed to send message');
    } catch (error) {
      if (axios.isAxiosError(error)) {
        const axiosError = error as AxiosError<{ detail: string }>;
        const errorDetail = axiosError.response?.data?.detail || '';
        
        // Check for Gemini API quota errors
        if (errorDetail.includes('quota') || errorDetail.includes('429')) {
          throw new Error(
            'O assistente de IA está temporariamente indisponível (limite de uso da API atingido). Por favor, tente novamente mais tarde.'
          );
        }
        
        throw new Error(errorDetail || 'Erro ao enviar mensagem');
      }
      
      throw error;
    }
  }
}

export const chatService = new ChatService();
