import { useState, useEffect, useRef } from 'react'

interface ChatInterfaceProps {
  onTasksUpdate: () => void
}

interface Message {
  role: 'user' | 'assistant'
  content: string
}

const API_URL = 'http://localhost:8000'

function ChatInterface({ onTasksUpdate }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Load saved conversation on mount
  useEffect(() => {
    fetch(`${API_URL}/conversation`)
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setMessages(data)
        }
      })
      .catch(() => {
        // Ignore errors loading conversation
      })
  }, [])

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!input.trim() || loading) return

    const userMessage = input.trim()
    setInput('')
    const newMessages = [...messages, { role: 'user' as const, content: userMessage }]
    setMessages(newMessages)
    setLoading(true)

    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: newMessages }),
      })
      const data = await res.json()

      setMessages([...newMessages, { role: 'assistant', content: data.response }])
      onTasksUpdate()
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: 'Error connecting to server' },
      ])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="chat-panel">
      <h2>Chat</h2>
      <div className="chat-messages">
        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role}`}>
            {msg.content}
          </div>
        ))}
        {loading && <div className="message assistant">Thinking...</div>}
        <div ref={messagesEndRef} />
      </div>
      <form className="chat-input-form" onSubmit={handleSubmit}>
        <input
          type="text"
          className="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask me to create, complete, or delete tasks..."
          disabled={loading}
        />
        <button type="submit" className="chat-send-btn" disabled={loading}>
          Send
        </button>
      </form>
    </div>
  )
}

export default ChatInterface
