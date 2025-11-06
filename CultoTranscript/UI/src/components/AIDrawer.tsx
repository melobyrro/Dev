import React, { useRef, useEffect } from 'react';
import { useChatStore } from '../stores/chatStore';
import { ChatMessage } from './ChatMessage';
import '../styles/AIDrawer.css';

export function AIDrawer() {
  const { messages, isOpen, isLoading, closeDrawer, sendMessage, refreshChat } = useChatStore();
  const [inputValue, setInputValue] = React.useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (isOpen && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [isOpen]);

  const handleSend = async () => {
    if (!inputValue.trim() || isLoading) return;

    const message = inputValue;
    setInputValue('');

    await sendMessage(message);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (!isOpen) return null;

  return (
    <>
      <div
        data-testid="drawer-overlay"
        className="drawer-backdrop"
        onClick={closeDrawer}
      />
      <div data-testid="ai-drawer" className="ai-drawer">
        <div className="drawer-header">
          <h2>Assistente IA</h2>
          <div className="drawer-actions">
            <button
              data-testid="new-conversation"
              className="icon-button"
              onClick={refreshChat}
              aria-label="Reiniciar conversa"
              title="Reiniciar conversa"
            >
              🔄
            </button>
            <button
              data-testid="drawer-close"
              className="icon-button"
              onClick={closeDrawer}
              aria-label="Fechar"
              title="Fechar"
            >
              ✕
            </button>
          </div>
        </div>

        <div className="drawer-body">
          {messages.length === 0 && (
            <div className="welcome-message">
              <p>Olá! Como posso ajudar você a explorar os sermões deste canal?</p>
            </div>
          )}

          {messages.map((message, index) => (
            <ChatMessage key={index} message={message} />
          ))}

          {isLoading && (
            <div data-testid="chat-loading" className="message message-assistant">
              <div className="message-content loading-indicator">
                <span className="loading-dot"></span>
                <span className="loading-dot"></span>
                <span className="loading-dot"></span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="drawer-footer">
          <textarea
            ref={textareaRef}
            data-testid="chat-input"
            className="chat-input"
            placeholder="Digite sua pergunta..."
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            rows={1}
            disabled={isLoading}
          />
          <button
            data-testid="send-button"
            className="send-button"
            onClick={handleSend}
            disabled={!inputValue.trim() || isLoading}
            aria-label="Enviar mensagem"
          >
            ➤
          </button>
        </div>
      </div>
    </>
  );
}
