import { create } from 'zustand';
import type { ChatMessage } from '../types';

interface ChatState {
  messages: ChatMessage[];
  isStreaming: boolean;

  addMessage: (message: ChatMessage) => void;
  updateLastMessage: (contentChunk: string) => void;
  setStreaming: (streaming: boolean) => void;
  clearMessages: () => void;
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  isStreaming: false,

  addMessage: (message) =>
    set((state) => ({ messages: [...state.messages, message] })),

  updateLastMessage: (contentChunk) =>
    set((state) => {
      if (state.messages.length === 0) return state;
      const updated = [...state.messages];
      const last = updated[updated.length - 1];
      updated[updated.length - 1] = {
        ...last,
        content: last.content + contentChunk,
      };
      return { messages: updated };
    }),

  setStreaming: (streaming) => set({ isStreaming: streaming }),

  clearMessages: () => set({ messages: [] }),
}));
