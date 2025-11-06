import type { ChatMessageDTO } from '../types';

interface ChatMessageProps {
  message: ChatMessageDTO;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user';

  const formattedTime = new Date(message.timestamp).toLocaleTimeString('pt-BR', {
    hour: '2-digit',
    minute: '2-digit',
  });

  return (
    <div
      data-testid={isUser ? 'user-message' : 'assistant-message'}
      className={'flex mb-4 ' + (isUser ? 'justify-end' : 'justify-start')}
    >
      <div className={'max-w-[80%] ' + (isUser ? 'order-2' : 'order-1')}>
        <div
          className={
            'rounded-lg px-4 py-2 ' +
            (isUser
              ? 'bg-indigo-600 text-white'
              : 'bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white')
          }
        >
          <div className="whitespace-pre-wrap break-words">{message.content}</div>
        </div>
        <div
          className={
            'text-xs text-gray-500 dark:text-gray-400 mt-1 ' +
            (isUser ? 'text-right' : 'text-left')
          }
        >
          {formattedTime}
        </div>
      </div>
    </div>
  );
}
