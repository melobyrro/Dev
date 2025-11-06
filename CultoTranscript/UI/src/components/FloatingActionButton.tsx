import { useChatStore } from '../stores/chatStore';
import '../styles/FloatingActionButton.css';

export function FloatingActionButton() {
  const openDrawer = useChatStore((state) => state.openDrawer);

  return (
    <button
      data-testid="ai-fab"
      className="fab"
      onClick={openDrawer}
      aria-label="Abrir Assistente IA"
    >
      💬
    </button>
  );
}
