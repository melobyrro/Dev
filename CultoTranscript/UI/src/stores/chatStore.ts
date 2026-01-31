import { create } from 'zustand';
import { chatService } from '../services/chatService';
import { config } from '../lib/config';
import type { ChatMessageDTO } from '../types';

interface ChatStore {
  messages: ChatMessageDTO[];
  isOpen: boolean;
  isLoading: boolean;
  sessionId: string;
  knowledgeMode: 'database_only' | 'global';
  drawerWidth: number;

  openDrawer: () => void;
  closeDrawer: () => void;
  sendMessage: (message: string) => Promise<void>;
  refreshChat: () => void;
  setKnowledgeMode: (mode: 'database_only' | 'global') => void;
  setDrawerWidth: (width: number) => void;
}

function generateSessionId(): string {
  return Date.now().toString() + '-' + Math.random().toString(36).substring(2, 9);
}

export const useChatStore = create<ChatStore>((set, get) => ({
  messages: [],
  isOpen: false,
  isLoading: false,
  sessionId: generateSessionId(),
  knowledgeMode: 'database_only',
  drawerWidth: parseInt(localStorage.getItem('chatbotPanelWidth') || '400', 10),

  openDrawer: () => set({ isOpen: true }),

  closeDrawer: () => set({ isOpen: false }),

  setKnowledgeMode: (mode) => set({ knowledgeMode: mode }),

  setDrawerWidth: (width) => {
    localStorage.setItem('chatbotPanelWidth', width.toString());
    set({ drawerWidth: width });
  },

  sendMessage: async (message: string) => {
    const { sessionId, messages, knowledgeMode } = get();

    const userMessage: ChatMessageDTO = {
      role: 'user',
      content: message,
      timestamp: new Date().toISOString(),
    };

    set({ messages: [...messages, userMessage], isLoading: true });

    try {
      const response = await chatService.sendMessage(
        config.defaultChannelId,
        message,
        sessionId,
        knowledgeMode
      );
      
      const assistantMessage: ChatMessageDTO = {
        role: 'assistant',
        content: response.response,
        timestamp: new Date().toISOString(),
      };
      
      set((state) => ({
        messages: [...state.messages, assistantMessage],
        isLoading: false,
        sessionId: response.session_id,
      }));
    } catch (error) {
      const errorMessage: ChatMessageDTO = {
        role: 'assistant',
        content: 'Desculpe, ocorreu um erro ao processar sua mensagem. Por favor, tente novamente.',
        timestamp: new Date().toISOString(),
      };
      
      set((state) => ({
        messages: [...state.messages, errorMessage],
        isLoading: false,
      }));
    }
  },
  
  refreshChat: () => set({ 
    messages: [], 
    sessionId: generateSessionId(),
  }),
}));
