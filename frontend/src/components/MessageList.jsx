import React from 'react';

function formatTimestamp(ts) {
  if (!ts) return null;
  const dt = new Date(ts);
  if (Number.isNaN(dt.getTime())) return null;
  return dt.toLocaleString();
}

function CitationPills({ citations }) {
  if (!citations || citations.length === 0) return null;
  const deduped = citations.filter(
    (c, i, arr) => arr.findIndex(x => x.source === c.source && x.chunk_id === c.chunk_id) === i
  );
  return (
    <div className="flex flex-wrap gap-1 mt-2">
      {deduped.map((c, i) => (
        <span
          key={i}
          title={`${c.source} — chunk ${c.chunk_id}`}
          className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-indigo-900 text-indigo-200 border border-indigo-700 font-mono"
        >
          <span className="opacity-60">§</span>
          {c.source.replace(/_seed$/, '').replace(/_/g, ' ')}
        </span>
      ))}
    </div>
  );
}

export default function MessageList({ messages }) {
  return (
    <ul className="space-y-4">
      {messages.map((m, i) => (
        <li key={i} className={m.role === 'user' ? 'text-right' : 'text-left'}>
          <div className={`inline-block px-3 py-2 rounded-lg text-sm leading-relaxed whitespace-pre-line ${m.role === 'user' ? 'bg-indigo-600 text-white' : 'bg-gray-800 text-gray-100 border border-gray-700'}`}>
            {m.content}
            {m.role === 'assistant' && <CitationPills citations={m.citations} />}
            {formatTimestamp(m.timestamp) && (
              <div className="mt-2 text-[10px] opacity-70">{formatTimestamp(m.timestamp)}</div>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}
