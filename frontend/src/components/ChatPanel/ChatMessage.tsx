import { memo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import clsx from 'clsx';
import type { ChatMessage as ChatMessageType } from '../../types';
import type { Components } from 'react-markdown';
import type { CSSProperties } from 'react';

interface ChatMessageProps {
  message: ChatMessageType;
}

const markdownComponents: Components = {
  code({ className, children, ...props }) {
    const match = /language-(\w+)/.exec(className ?? '');
    const inline = !match && !className;

    if (inline) {
      return (
        <code
          className="rounded-none bg-canvas-inset px-1 py-0.5 font-mono text-xs text-accent-fg border border-border-muted"
          {...props}
        >
          {children}
        </code>
      );
    }

    const language = match ? match[1] : 'text';

    return (
      <SyntaxHighlighter
        style={oneDark as Record<string, CSSProperties>}
        language={language}
        PreTag="div"
        customStyle={{
          margin: '0.5rem 0',
          borderRadius: '0',
          fontSize: '11px',
          border: '1px solid #21262d',
          background: '#010409',
        }}
      >
        {String(children).replace(/\n$/, '')}
      </SyntaxHighlighter>
    );
  },
  p({ children }) {
    return <p className="mb-2 last:mb-0 leading-relaxed text-xs">{children}</p>;
  },
  ul({ children }) {
    return <ul className="mb-2 list-disc pl-4 space-y-1 text-xs">{children}</ul>;
  },
  ol({ children }) {
    return <ol className="mb-2 list-decimal pl-4 space-y-1 text-xs">{children}</ol>;
  },
  li({ children }) {
    return <li className="text-xs">{children}</li>;
  },
  strong({ children }) {
    return <strong className="font-semibold text-fg-default">{children}</strong>;
  },
  em({ children }) {
    return <em className="text-fg-muted italic">{children}</em>;
  },
  blockquote({ children }) {
    return (
      <blockquote className="border-l-2 border-accent-fg pl-3 text-fg-muted italic my-2 text-xs">
        {children}
      </blockquote>
    );
  },
  h1({ children }) {
    return <h1 className="text-sm font-bold text-fg-default mb-2 mt-3">{children}</h1>;
  },
  h2({ children }) {
    return <h2 className="text-xs font-bold text-fg-default mb-1.5 mt-2">{children}</h2>;
  },
  h3({ children }) {
    return <h3 className="text-xs font-semibold text-fg-muted mb-1 mt-2">{children}</h3>;
  },
  hr() {
    return <hr className="border-border-muted my-3" />;
  },
};

export const ChatMessage = memo(function ChatMessage({
  message,
}: ChatMessageProps) {
  const isUser = message.role === 'user';

  return (
    <div
      className="flex w-full"
      role="article"
      aria-label={`${isUser ? 'Your' : 'Assistant'} message`}
    >
      <div
        className={clsx(
          'max-w-[85%] px-3 py-2 text-xs',
          isUser
            ? 'bg-[#1f2d3d] text-fg-default border-l-[3px] border-l-accent-fg ml-auto'
            : 'bg-canvas-subtle text-fg-default border-l-[3px] border-l-border-default'
        )}
      >
        {isUser ? (
          <p className="font-mono text-xs leading-relaxed">{message.content}</p>
        ) : (
          <div className="prose prose-invert max-w-none text-xs">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={markdownComponents}
            >
              {message.content}
            </ReactMarkdown>
            {message.isStreaming && (
              <span
                className="cursor-blink inline-block font-mono text-fg-muted ml-0.5 align-middle"
                aria-hidden="true"
              >
                |
              </span>
            )}
          </div>
        )}
        <time
          className="mt-1 block text-right font-mono text-[10px] text-fg-subtle"
          dateTime={message.timestamp.toISOString()}
        >
          {message.timestamp.toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </time>
      </div>
    </div>
  );
});
