import { useState, useEffect, useRef } from 'react'
import { useFeatureFlag } from '../featureFlags'
import Icon from './Icon'

// Props support both legacy (collapsed strip) and v2 (overlay slide-in) modes.
// When ux_v2.chat_overlay=true: `visible` and `onClose` drive behavior.
// When false: legacy `collapsed` and `onToggleCollapse` still work.
interface ChatInterfaceProps {
  onTasksUpdate: () => void
  // Legacy props
  collapsed?: boolean
  onToggleCollapse?: () => void
  // v2 overlay props
  visible?: boolean
  onClose?: () => void
}

interface Message {
  role: 'user' | 'assistant'
  content: string
}

interface ConversationSummary {
  id: number
  title: string
}

interface HistoryPopup {
  conversations: ConversationSummary[]
  x: number
  y: number
}

const API_URL = 'http://localhost:8000'

function HistoryDrawer({
  conversations,
  activeId,
  onSwitch,
  onClose,
}: {
  conversations: ConversationSummary[]
  activeId: number | null
  onSwitch: (id: number) => void
  onClose: () => void
}) {
  return (
    <div className="history-drawer" role="complementary" aria-label="Conversation history">
      <div className="history-drawer-header">
        <span className="history-drawer-title">All Chats</span>
        <button className="history-drawer-close" onClick={onClose} type="button" aria-label="Close history">
          <Icon n="close" size={14} />
        </button>
      </div>
      <div className="history-drawer-list">
        {conversations.length === 0 && (
          <div className="history-drawer-empty">No conversations yet.</div>
        )}
        {conversations.map(c => (
          <div
            key={c.id}
            className={`history-drawer-item${c.id === activeId ? ' history-drawer-item--active' : ''}`}
            onClick={() => { onSwitch(c.id); onClose() }}
          >
            {c.title || 'Untitled'}
          </div>
        ))}
      </div>
    </div>
  )
}

function ChatInterface({
  onTasksUpdate,
  collapsed = false,
  onToggleCollapse = () => {},
  visible,
  onClose,
}: ChatInterfaceProps) {
  const uxV2 = useFeatureFlag('ux_v2')
  const chatOverlayFlag = useFeatureFlag('ux_v2.chat_overlay')
  const chatOverlay = uxV2 && chatOverlayFlag

  const [messages, setMessages] = useState<Message[]>([])
  const [activeConversationId, setActiveConversationId] = useState<number | null>(null)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [historyPopup, setHistoryPopup] = useState<HistoryPopup | null>(null)
  const [allChats, setAllChats] = useState<ConversationSummary[] | null>(null)
  const [historyDrawerOpen, setHistoryDrawerOpen] = useState(false)
  const [historyDrawerConvs, setHistoryDrawerConvs] = useState<ConversationSummary[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const historyBtnRef = useRef<HTMLButtonElement>(null)
  const historyPopupRef = useRef<HTMLDivElement>(null)

  // Start a fresh conversation on mount
  useEffect(() => {
    fetch(`${API_URL}/conversation/new`, { method: 'POST' })
      .then(res => res.json())
      .then(data => setActiveConversationId(data.id))
      .catch(() => {})
  }, [])

  // Close history popup on outside click (legacy mode)
  useEffect(() => {
    if (!historyPopup) return
    function handleOutsideClick(e: MouseEvent) {
      if (historyBtnRef.current?.contains(e.target as Node)) return
      if (historyPopupRef.current?.contains(e.target as Node)) return
      setHistoryPopup(null)
    }
    document.addEventListener('mousedown', handleOutsideClick)
    return () => document.removeEventListener('mousedown', handleOutsideClick)
  }, [historyPopup])

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  async function handleNewChat() {
    if (loading) return
    try {
      const res = await fetch(`${API_URL}/conversation/new`, { method: 'POST' })
      const data = await res.json()
      setMessages([])
      setActiveConversationId(data.id)
    } catch {}
  }

  async function openHistoryDrawer() {
    try {
      const res = await fetch(`${API_URL}/conversations`)
      const data: ConversationSummary[] = await res.json()
      setHistoryDrawerConvs(data)
      setHistoryDrawerOpen(true)
    } catch {}
  }

  async function handleHistoryClick(e: React.MouseEvent<HTMLButtonElement>) {
    if (chatOverlay) {
      await openHistoryDrawer()
      return
    }
    if (historyPopup) { setHistoryPopup(null); return }
    const rect = e.currentTarget.getBoundingClientRect()
    try {
      const res = await fetch(`${API_URL}/conversations?limit=3`)
      const data: ConversationSummary[] = await res.json()
      setHistoryPopup({ conversations: data, x: rect.right, y: rect.bottom + 6 })
    } catch {}
  }

  async function handleAllChatsClick() {
    setHistoryPopup(null)
    try {
      const res = await fetch(`${API_URL}/conversations`)
      const data: ConversationSummary[] = await res.json()
      setAllChats(data)
    } catch {}
  }

  async function switchConversation(id: number) {
    setHistoryPopup(null)
    setAllChats(null)
    setHistoryDrawerOpen(false)
    try {
      const res = await fetch(`${API_URL}/conversations/${id}`)
      const data = await res.json()
      setActiveConversationId(data.id)
      setMessages(Array.isArray(data.messages) ? data.messages : [])
    } catch {}
  }

  async function sendMessage(text: string) {
    if (!text.trim() || loading) return
    const userMessage = text.trim()
    setInput('')
    const newMessages = [...messages, { role: 'user' as const, content: userMessage }]
    setMessages(newMessages)
    setLoading(true)
    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: newMessages, conversation_id: activeConversationId }),
      })
      const data = await res.json()
      setMessages([...newMessages, { role: 'assistant', content: data.response }])
      onTasksUpdate()
      if (data.title && activeConversationId !== null) {
        const applyTitle = (convs: ConversationSummary[]) =>
          convs.map(c => c.id === activeConversationId ? { ...c, title: data.title } : c)
        setHistoryPopup(prev => prev ? { ...prev, conversations: applyTitle(prev.conversations) } : null)
        setAllChats(prev => prev ? applyTitle(prev) : null)
        setHistoryDrawerConvs(prev => applyTitle(prev))
      }
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Error connecting to server' }])
    } finally {
      setLoading(false)
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    await sendMessage(input)
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(input)
    }
  }

  // ── v2 overlay layout ────────────────────────────────────────────────────
  if (chatOverlay) {
    const isVisible = visible ?? false
    return (
      <div
        className="chat-panel chat-panel--overlay"
        style={{
          transform: isVisible ? 'translateX(0)' : 'translateX(102%)',
          transition: 'transform 0.38s cubic-bezier(0.4,0,0.2,1)',
        }}
        aria-hidden={!isVisible}
      >
        {/* v2 header */}
        <div className="chat-header chat-header--v2">
          <button
            className="chat-close-btn"
            onClick={onClose}
            title="Close chat"
            type="button"
            aria-label="Close chat"
          >
            <Icon n="chevR" size={16} />
          </button>
          <div className="chat-header-title">
            <span className="chat-header-label">AI Assistant</span>
            <span className="chat-online-dot" title="Online" />
          </div>
          <div className="chat-header-actions">
            <button
              ref={historyBtnRef}
              className="history-btn"
              onClick={handleHistoryClick}
              title="Chat history"
              type="button"
            >
              <Icon n="history" size={16} />
            </button>
            <button
              className="new-chat-btn"
              onClick={handleNewChat}
              disabled={loading}
              title="Start a new conversation"
              type="button"
            >
              + New
            </button>
          </div>
        </div>

        {/* History drawer (replaces inline popover in v2) */}
        {historyDrawerOpen && (
          <HistoryDrawer
            conversations={historyDrawerConvs}
            activeId={activeConversationId}
            onSwitch={switchConversation}
            onClose={() => setHistoryDrawerOpen(false)}
          />
        )}

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
          <textarea
            className="chat-input chat-input--textarea"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask me to create, complete, or delete tasks..."
            disabled={loading}
            rows={1}
          />
          <button type="submit" className="chat-send-btn" disabled={loading || !input.trim()}>
            <Icon n="send" size={16} />
          </button>
        </form>
      </div>
    )
  }

  // ── Legacy layout ────────────────────────────────────────────────────────
  return (
    <div className={`chat-panel${collapsed ? ' collapsed' : ''}`}>
      <div className="chat-header">
        <button
          className="chat-collapse-btn"
          onClick={onToggleCollapse}
          title={collapsed ? 'Expand chat' : 'Collapse chat'}
          type="button"
        >
          {collapsed ? '<' : '>'}
        </button>
        <h2>Chat</h2>
        <div className="chat-header-actions">
          <button
            ref={historyBtnRef}
            className="history-btn"
            onClick={handleHistoryClick}
            title="Chat history"
            type="button"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
              <path d="M3 3v5h5" />
              <path d="M12 7v5l4 2" />
            </svg>
          </button>
          <button
            className="new-chat-btn"
            onClick={handleNewChat}
            disabled={loading}
            title="Start a new conversation"
          >
            New Chat
          </button>
        </div>
      </div>
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
          onChange={e => setInput(e.target.value)}
          placeholder="Ask me to create, complete, or delete tasks..."
          disabled={loading}
        />
        <button type="submit" className="chat-send-btn" disabled={loading}>
          Send
        </button>
      </form>

      {historyPopup && (
        <div
          ref={historyPopupRef}
          className="history-popup"
          style={{
            left: historyPopup.x,
            top: Math.max(8, Math.min(historyPopup.y, window.innerHeight - 200)),
            transform: 'translateX(-100%)',
          }}
        >
          {historyPopup.conversations.map(c => (
            <div
              key={c.id}
              className={`history-popup-item${c.id === activeConversationId ? ' history-popup-item--active' : ''}`}
              onClick={() => switchConversation(c.id)}
            >
              {c.title || 'Untitled'}
            </div>
          ))}
          <div className="history-popup-item history-popup-all" onClick={handleAllChatsClick}>
            All Chats
          </div>
        </div>
      )}

      {allChats !== null && (
        <div className="all-chats-overlay" onClick={() => setAllChats(null)}>
          <div className="all-chats-modal" onClick={e => e.stopPropagation()}>
            <div className="all-chats-header">
              <span>All Chats</span>
              <button className="all-chats-close" onClick={() => setAllChats(null)} type="button">✕</button>
            </div>
            <div className="all-chats-list">
              {allChats.length === 0 && <div className="all-chats-empty">No conversations yet.</div>}
              {allChats.map(c => (
                <div
                  key={c.id}
                  className={`all-chats-item${c.id === activeConversationId ? ' all-chats-item--active' : ''}`}
                  onClick={() => switchConversation(c.id)}
                >
                  {c.title || 'Untitled'}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default ChatInterface
