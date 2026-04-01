import {
  BarChart, Bar,
  LineChart, Line,
  AreaChart, Area,
  PieChart, Pie, Cell,
  ScatterChart, Scatter, ZAxis,
  XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts'

const COLORS = ['#4f6ef7', '#34d399', '#f59e0b', '#f87171', '#a78bfa', '#38bdf8']

// Convert raw rows + columns into recharts-friendly [{col: val}] format
function toChartData(columns, rows) {
  return rows.map(row =>
    Object.fromEntries(columns.map((col, i) => [col, row[i]]))
  )
}

export default function ChartRenderer({ result }) {
  const { visualization, visualization_config: cfg, columns, rows } = result
  const data   = toChartData(columns, rows)
  const xKey   = cfg?.x_axis   || columns[0]
  const yKeys  = cfg?.y_axis?.length ? cfg.y_axis : columns.filter(c => c !== xKey)
  const title  = cfg?.title    || ''

  const commonProps = {
    data,
    margin: { top: 10, right: 20, left: 0, bottom: 5 },
  }

  const renderChart = () => {
    switch (visualization) {

      case 'bar_chart':
        return (
          <BarChart {...commonProps}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey={xKey} tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip />
            <Legend />
            {yKeys.map((k, i) => (
              <Bar key={k} dataKey={k} fill={COLORS[i % COLORS.length]} radius={[4,4,0,0]} />
            ))}
          </BarChart>
        )

      case 'line_chart':
        return (
          <LineChart {...commonProps}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey={xKey} tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip />
            <Legend />
            {yKeys.map((k, i) => (
              <Line key={k} type="monotone" dataKey={k}
                stroke={COLORS[i % COLORS.length]} strokeWidth={2} dot={{ r: 4 }} />
            ))}
          </LineChart>
        )

      case 'area_chart':
        return (
          <AreaChart {...commonProps}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey={xKey} tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip />
            <Legend />
            {yKeys.map((k, i) => (
              <Area key={k} type="monotone" dataKey={k}
                stroke={COLORS[i % COLORS.length]}
                fill={COLORS[i % COLORS.length] + '33'}
                strokeWidth={2} />
            ))}
          </AreaChart>
        )

      case 'pie_chart': {
        const labelKey = cfg?.label || columns[0]
        const valueKey = yKeys[0]   || columns[1]
        return (
          <PieChart>
            <Pie data={data} dataKey={valueKey} nameKey={labelKey}
              cx="50%" cy="50%" outerRadius={130} label>
              {data.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip />
            <Legend />
          </PieChart>
        )
      }

      case 'scatter_chart': {
        const [xK, yK] = columns
        return (
          <ScatterChart {...commonProps}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey={xK} name={xK} tick={{ fontSize: 12 }} />
            <YAxis dataKey={yK} name={yK} tick={{ fontSize: 12 }} />
            <ZAxis range={[60, 60]} />
            <Tooltip cursor={{ strokeDasharray: '3 3' }} />
            <Scatter data={data} fill={COLORS[0]} />
          </ScatterChart>
        )
      }

      default:
        return null
    }
  }

  if (visualization === 'table' || !renderChart()) {
    return (
      <div className="overflow-x-auto rounded-lg border border-gray-200">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              {columns.map(c => (
                <th key={c} className="px-4 py-3 text-left font-medium text-gray-500 uppercase tracking-wide text-xs">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {rows.map((row, i) => (
              <tr key={i} className="hover:bg-gray-50 transition-colors">
                {row.map((cell, j) => (
                  <td key={j} className="px-4 py-3 text-gray-700">
                    {cell === null ? <span className="text-gray-300">—</span> : String(cell)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  return (
    <div>
      {title && <p className="text-sm font-medium text-gray-500 mb-3">{title}</p>}
      <ResponsiveContainer width="100%" height={320}>
        {renderChart()}
      </ResponsiveContainer>
    </div>
  )
}