import { useState, useEffect, useRef } from "react";

interface QuickEntryProps {
  onClose: () => void;
  onTasksUpdate: () => void;
}

const API_URL = "http://localhost:8000";

function QuickEntry({ onClose, onTasksUpdate }: QuickEntryProps) {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const overlayRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Close on Escape
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  function handleOverlayClick(e: React.MouseEvent<HTMLDivElement>) {
    if (e.target === overlayRef.current) onClose();
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || loading) return;

    setLoading(true);
    setFeedback(null);
    try {
      const convRes = await fetch(`${API_URL}/conversation/new`, {
        method: "POST",
      });
      const convData = await convRes.json();
      const conversationId: number = convData.id;

      const res = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: [{ role: "user", content: text }],
          conversation_id: conversationId,
        }),
      });
      const data = await res.json();
      onTasksUpdate();
      setFeedback(data.response ?? "Done");
      setInput("");
      // Auto-close after brief feedback delay
      setTimeout(onClose, 3000);
    } catch {
      setFeedback("Error connecting to server");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      className="quick-entry-overlay"
      ref={overlayRef}
      onClick={handleOverlayClick}
    >
      <div className="quick-entry-popup">
        <form onSubmit={handleSubmit}>
          <input
            ref={inputRef}
            className="quick-entry-input"
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Create a task..."
            disabled={loading}
          />
        </form>
        {feedback && <div className="quick-entry-feedback">{feedback}</div>}
        <div className="quick-entry-hint">Enter to submit · Esc to dismiss</div>
      </div>
    </div>
  );
}

export default QuickEntry;
