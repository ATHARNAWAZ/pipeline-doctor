import { useCallback, useEffect, useRef } from 'react';
import { useChatStore } from '../stores/chatStore';
import type { ChatMessage } from '../types';

// In production set VITE_WS_URL to point directly at the backend WebSocket
// (e.g. wss://your-backend.onrender.com/query/stream).
// In dev, fall back to the Vite proxy path so no env var is needed locally.
const WS_PROTOCOL = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const WS_URL =
  import.meta.env.VITE_WS_URL ??
  `${WS_PROTOCOL}//${window.location.host}/ws/query/stream`;
const RECONNECT_BASE_DELAY_MS = 1000;
const RECONNECT_MAX_DELAY_MS = 30000;
const MAX_RECONNECT_ATTEMPTS = 5;

interface StreamPayload {
  chunk?: string;
  done?: boolean;
  error?: string;
}

function generateId(): string {
  return `msg_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

export function useStreamingChat(analysisId: string | null) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingQuestionRef = useRef<{
    question: string;
    analysisId: string | null;
  } | null>(null);
  const isMountedRef = useRef(true);

  const { addMessage, updateLastMessage, setStreaming, isStreaming } =
    useChatStore();

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimerRef.current !== null) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    if (wsRef.current?.readyState === WebSocket.CONNECTING) return;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      reconnectAttemptsRef.current = 0;

      // If there's a pending question, send it now
      if (pendingQuestionRef.current && ws.readyState === WebSocket.OPEN) {
        const { question, analysisId } = pendingQuestionRef.current;
        pendingQuestionRef.current = null;
        ws.send(JSON.stringify({ question, analysis_id: analysisId }));
      }
    };

    ws.onmessage = (event: MessageEvent<string>) => {
      if (!isMountedRef.current) return;

      let payload: StreamPayload;
      try {
        payload = JSON.parse(event.data) as StreamPayload;
      } catch {
        return;
      }

      if (payload.error) {
        updateLastMessage(`\n\n*Error: ${payload.error}*`);
        setStreaming(false);
        return;
      }

      if (payload.chunk) {
        updateLastMessage(payload.chunk);
      }

      if (payload.done) {
        setStreaming(false);
        // Mark the last message as no longer streaming
        useChatStore.setState((state) => {
          if (state.messages.length === 0) return state;
          const updated = [...state.messages];
          updated[updated.length - 1] = {
            ...updated[updated.length - 1],
            isStreaming: false,
          };
          return { messages: updated };
        });
      }
    };

    ws.onerror = () => {
      // onclose will fire after onerror, handle reconnect there
    };

    ws.onclose = () => {
      if (!isMountedRef.current) return;
      if (isStreaming) {
        setStreaming(false);
      }

      // Reconnect with exponential backoff if within attempts limit
      if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
        const delay = Math.min(
          RECONNECT_BASE_DELAY_MS * Math.pow(2, reconnectAttemptsRef.current),
          RECONNECT_MAX_DELAY_MS
        );
        reconnectAttemptsRef.current += 1;
        reconnectTimerRef.current = setTimeout(() => {
          if (isMountedRef.current) {
            connect();
          }
        }, delay);
      }
    };
  }, [updateLastMessage, setStreaming, isStreaming]);

  useEffect(() => {
    isMountedRef.current = true;
    // Only connect once an analysis exists — avoids noisy connection errors on initial load
    if (analysisId) {
      connect();
    }

    return () => {
      isMountedRef.current = false;
      clearReconnectTimer();
      if (wsRef.current) {
        wsRef.current.onclose = null; // prevent reconnect on intentional close
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [analysisId, connect, clearReconnectTimer]);

  const sendMessage = useCallback(
    (question: string, analysisId: string | null) => {
      // Add user message
      const userMessage: ChatMessage = {
        id: generateId(),
        role: 'user',
        content: question,
        timestamp: new Date(),
      };
      addMessage(userMessage);

      // Add placeholder assistant message for streaming
      const assistantMessage: ChatMessage = {
        id: generateId(),
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        isStreaming: true,
      };
      addMessage(assistantMessage);
      setStreaming(true);

      const payload = JSON.stringify({ question, analysis_id: analysisId });

      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(payload);
      } else {
        // Queue the question and attempt reconnection
        pendingQuestionRef.current = { question, analysisId };
        connect();
      }
    },
    [addMessage, setStreaming, connect]
  );

  return { sendMessage, isStreaming };
}
