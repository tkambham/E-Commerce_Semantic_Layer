import { useState } from 'react'
import ChartRenderer from './ChartRenderer'
import { ChevronDown, ChevronUp, Database } from 'lucide-react'

export default function MessageBubble({ msg }) {

  // ── User bubble ───────────────────────────────────────────
  if (msg.type === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-xl bg-brand-500 text-white px-4 py-2.5 rounded-2xl rounded-br-sm text-sm shadow-sm">
          {msg.text}
        </div>
      </div>
    )
  }

  // ── Error bubble ──────────────────────────────────────────
  if (msg.type === 'error') {
    return (
      <div className="flex justify-start">
        <div className="max-w-xl bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-2xl rounded-bl-sm text-sm">
          <span className="font-medium">Error: </span>{msg.text}
        </div>
      </div>
    )
  }

  // ── Assistant result bubble ───────────────────────────────
  return <ResultBubble result={msg.result} />
}

function ResultBubble({ result }) {
  const [sqlOpen, setSqlOpen] = useState(false)
  const hasData = result.rows?.length > 0

  return (
    <div className="flex justify-start w-full">
      <div className="w-full max-w-4xl bg-white border border-gray-200 rounded-2xl rounded-bl-sm shadow-sm overflow-hidden">

        {/* Header */}
        <div className="flex items-center gap-2 px-5 py-3 border-b border-gray-100 bg-gray-50">
          <Database size={14} className="text-brand-500" />
          <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
            {result.kpi_set_name}
          </span>
          <span className="ml-auto text-xs text-gray-400">
            {result.rows?.length ?? 0} row{result.rows?.length !== 1 ? 's' : ''}
          </span>
        </div>

        {/* Chart or table */}
        <div className="p-5">
          {hasData
            ? <ChartRenderer result={result} />
            : <p className="text-sm text-gray-400 text-center py-8">No data found for this query.</p>
          }
        </div>

        {/* SQL toggle */}
        <div className="border-t border-gray-100">
          <button
            onClick={() => setSqlOpen(o => !o)}
            className="w-full flex items-center gap-2 px-5 py-2.5 text-xs text-gray-400 hover:text-gray-600 hover:bg-gray-50 transition-colors text-left"
          >
            {sqlOpen ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
            {sqlOpen ? 'Hide' : 'Show'} generated SQL
          </button>
          {sqlOpen && (
            <pre className="px-5 pb-4 text-xs font-mono text-gray-600 bg-gray-50 whitespace-pre-wrap break-all leading-relaxed">
              {result.refined_sql}
            </pre>
          )}
        </div>

      </div>
    </div>
  )
}