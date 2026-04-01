import { MessageSquare, Trash2, BarChart2 } from 'lucide-react'

export default function Sidebar({ history, activeId, onSelect, onClear }) {
  return (
    <aside className="w-64 shrink-0 h-screen bg-white border-r border-gray-200 flex flex-col">

      {/* Logo */}
      <div className="flex items-center gap-2.5 px-5 py-4 border-b border-gray-100">
        <div className="w-7 h-7 rounded-lg bg-brand-500 flex items-center justify-center">
          <BarChart2 size={14} className="text-white" />
        </div>
        <span className="font-semibold text-gray-800 text-sm">QueryAI</span>
      </div>

      {/* History list */}
      <div className="flex-1 overflow-y-auto py-3 px-2">
        {history.length === 0 ? (
          <p className="text-xs text-gray-400 text-center mt-8 px-4">
            Your query history will appear here.
          </p>
        ) : (
          <ul className="space-y-0.5">
            {history.map(item => (
              <li key={item.id}>
                <button
                  onClick={() => onSelect(item.id)}
                  className={`w-full flex items-start gap-2.5 px-3 py-2.5 rounded-lg text-left transition-colors text-sm ${
                    activeId === item.id
                      ? 'bg-brand-50 text-brand-700'
                      : 'text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  <MessageSquare size={13} className="mt-0.5 shrink-0 opacity-60" />
                  <span className="truncate leading-snug">{item.question}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Clear */}
      {history.length > 0 && (
        <div className="px-3 py-3 border-t border-gray-100">
          <button
            onClick={onClear}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs text-gray-400 hover:text-red-500 hover:bg-red-50 transition-colors"
          >
            <Trash2 size={13} />
            Clear history
          </button>
        </div>
      )}

    </aside>
  )
}