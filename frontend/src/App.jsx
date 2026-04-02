import { useState, useRef, useEffect } from 'react'
import { SendHorizonal, Loader2 } from 'lucide-react'
import Sidebar from './components/Sidebar'
import MessageBubble from './components/MessageBubble'
import { askQuery } from './api'

let _id = 0
const uid = () => ++_id

export default function App() {
  const [messages, setMessages]   = useState([])   // {id, type, text?, result?}
  const [history, setHistory]     = useState([])   // {id, question}
  const [activeId, setActiveId]   = useState(null)
  const [input, setInput]         = useState('')
  const [loading, setLoading]     = useState(false)
  const bottomRef                 = useRef(null)
  const inputRef                  = useRef(null)

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function handleSubmit(e) {
    e?.preventDefault()
    const q = input.trim()
    if (!q || loading) return

    const msgId = uid()
    setInput('')
    setActiveId(msgId)
    setLoading(true)

    // Add user bubble immediately
    setMessages(prev => [...prev, { id: msgId, type: 'user', text: q }])

    try {
      const result = await askQuery(q)
      const resId  = uid()
      setMessages(prev => [...prev, { id: resId, type: 'result', result }])
      setHistory(prev => [{ id: msgId, question: q }, ...prev])
    } catch (err) {
      setMessages(prev => [...prev, { id: uid(), type: 'error', text: err.message }])
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  function handleSelectHistory(id) {
    setActiveId(id)
    // Scroll to the message with this id
    document.getElementById(`msg-${id}`)?.scrollIntoView({ behavior: 'smooth' })
  }

  function handleClearHistory() {
    setMessages([])
    setHistory([])
    setActiveId(null)
  }

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50">

      {/* Sidebar */}
      <Sidebar
        history={history}
        activeId={activeId}
        onSelect={handleSelectHistory}
        onClear={handleClearHistory}
      />

      {/* Main */}
      <div className="flex flex-col flex-1 min-w-0">

        {/* Messages area */}
        <div className="flex-1 overflow-y-auto px-6 py-6 space-y-5">

          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center gap-3 select-none">
              <div className="w-12 h-12 rounded-2xl bg-brand-50 flex items-center justify-center">
                <SendHorizonal size={22} className="text-brand-500" />
              </div>
              <p className="text-gray-700 font-medium">Ask anything about your data</p>
              <p className="text-sm text-gray-400 max-w-sm">
                Try: "Show me total revenue for January 2025" or
                "What are the top selling products?"
              </p>
            </div>
          )}

          {messages.map(msg => (
            <div key={msg.id} id={`msg-${msg.id}`}>
              <MessageBubble msg={msg} />
            </div>
          ))}

          {/* Loading indicator */}
          {loading && (
            <div className="flex justify-start">
              <div className="bg-white border border-gray-200 rounded-2xl rounded-bl-sm px-4 py-3 flex items-center gap-2 shadow-sm">
                <Loader2 size={15} className="text-brand-500 animate-spin" />
                <span className="text-sm text-gray-400">Thinking...</span>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Input bar */}
        <div className="border-t border-gray-200 bg-white px-6 py-4">
          <form onSubmit={handleSubmit} className="flex items-end gap-3 max-w-4xl mx-auto">
            <div className="flex-1 relative">
              <textarea
                ref={inputRef}
                rows={1}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask a question about your data..."
                disabled={loading}
                className="w-full resize-none rounded-xl border border-gray-200 bg-gray-50 px-4 py-3 pr-12 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent disabled:opacity-50 leading-relaxed"
                style={{ maxHeight: '120px', overflowY: 'auto' }}
                onInput={e => {
                  e.target.style.height = 'auto'
                  e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px'
                }}
              />
            </div>
            <button
              type="submit"
              disabled={!input.trim() || loading}
              className="shrink-0 w-10 h-10 rounded-xl bg-brand-500 hover:bg-brand-600 disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center transition-colors shadow-sm"
            >
              {loading
                ? <Loader2 size={16} className="text-white animate-spin" />
                : <SendHorizonal size={16} className="text-white" />
              }
            </button>
          </form>
          <p className="text-center text-xs text-gray-300 mt-2">
            Press Enter to send · Shift+Enter for new line
          </p>
        </div>

      </div>
    </div>
  )
}