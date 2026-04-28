import {
  useRef,
  useEffect,
  useState,
  useCallback,
  type KeyboardEvent,
} from 'react';
import { Send, Trash2 } from 'lucide-react';
import clsx from 'clsx';
import { useChatStore } from '../../stores/chatStore';
import { usePipelineStore } from '../../stores/pipelineStore';
import { useStreamingChat } from '../../hooks/useStreamingChat';
import { ChatMessage } from './ChatMessage';

const PLACEHOLDER_TEXT =
  "Ask about your pipeline. Try: 'Why did mart_customer_ltv fail?'";
const EMPTY_STATE_TEXT =
  "Ask about your pipeline. Try: 'Why did mart_customer_ltv fail?'";

export function ChatPanel() {
  const { messages, isStreaming, clearMessages } = useChatStore();
  const { analysisId } = usePipelineStore();
  const { sendMessage } = useStreamingChat(analysisId);
  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom when messages update
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = useCallback(() => {
    const trimmed = inputValue.trim();
    if (!trimmed || isStreaming) return;
    setInputValue('');
    sendMessage(trimmed, analysisId);
  }, [inputValue, isStreaming, sendMessage, analysisId]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  const handleClear = useCallback(() => {
    clearMessages();
  }, [clearMessages]);

  const isInputDisabled = isStreaming;
  const isSendDisabled = isStreaming || !inputValue.trim();
  const hasInput = inputValue.trim().length > 0;

  return (
    <div className="flex h-full flex-col bg-canvas-default">
      {/* Header */}
      <div className="flex shrink-0 items-center justify-between border-b border-border-default px-3 py-2 bg-canvas-subtle">
        <h2 className="font-mono text-xs font-semibold uppercase tracking-widest text-fg-muted">
          Chat
        </h2>
        <button
          type="button"
          onClick={handleClear}
          disabled={messages.length === 0}
          className={clsx(
            'flex items-center gap-1 px-2 py-1 text-[10px] font-mono transition-colors',
            messages.length === 0
              ? 'text-fg-subtle cursor-not-allowed'
              : 'text-fg-muted hover:text-danger-fg hover:bg-danger-fg/10'
          )}
          aria-label="Clear chat messages"
          title="Clear messages"
        >
          <Trash2 size={11} aria-hidden="true" />
          clear
        </button>
      </div>

      {/* Messages scroll area */}
      <div
        className="flex-1 overflow-y-auto px-3 py-3 space-y-2"
        role="log"
        aria-label="Chat messages"
        aria-live="polite"
        aria-atomic="false"
      >
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <div className="mb-2 font-mono text-xl text-fg-subtle" aria-hidden="true">
              ✦
            </div>
            <p className="font-mono text-xs text-fg-muted max-w-[220px] leading-relaxed">
              {EMPTY_STATE_TEXT}
            </p>
            {!analysisId && (
              <p className="mt-2 font-mono text-[10px] text-fg-subtle">
                Upload a manifest first to enable analysis.
              </p>
            )}
          </div>
        ) : (
          messages.map((message) => (
            <ChatMessage key={message.id} message={message} />
          ))
        )}
        <div ref={messagesEndRef} aria-hidden="true" />
      </div>

      {/* Input area */}
      <div className="shrink-0 border-t border-border-default bg-canvas-inset px-3 py-2">
        <div className="flex items-end gap-2">
          <label htmlFor="chat-input" className="sr-only">
            Ask about your pipeline
          </label>
          <textarea
            id="chat-input"
            ref={inputRef}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={PLACEHOLDER_TEXT}
            disabled={isInputDisabled}
            rows={2}
            className={clsx(
              'flex-1 resize-none bg-transparent px-0 py-1',
              'font-mono text-xs text-fg-default placeholder:text-fg-subtle',
              'focus:outline-none border-none',
              'transition-colors scrollbar-thin',
              isInputDisabled ? 'opacity-60 cursor-not-allowed' : ''
            )}
            aria-label="Ask about your pipeline"
          />
          {/* Send button: only visually prominent when there is text */}
          <button
            type="button"
            onClick={handleSend}
            disabled={isSendDisabled}
            className={clsx(
              'flex h-8 w-8 shrink-0 items-center justify-center border transition-colors',
              hasInput && !isStreaming
                ? 'border-accent-fg/60 text-accent-fg hover:bg-accent-fg/10 hover:border-accent-fg'
                : 'border-border-muted text-fg-subtle cursor-not-allowed opacity-40'
            )}
            aria-label="Send message"
            title="Send (Enter)"
          >
            <Send size={13} aria-hidden="true" />
          </button>
        </div>
        {isStreaming && (
          <p className="mt-1 font-mono text-[10px] text-fg-subtle" role="status" aria-label="Analyzing, responding...">
            <span className="cursor-blink inline-block mr-1" aria-hidden="true">|</span>
            <span aria-hidden="true">responding...</span>
          </p>
        )}
      </div>
    </div>
  );
}
