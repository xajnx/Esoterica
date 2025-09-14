import React from 'react';

export default function MessageList({ messages }) {
  return (
    <ul className="space-y-4">
      {messages.map((m, i) => (
        <li key={i} className={m.role === 'user' ? 'text-right' : 'text-left'}>
          <div className={`inline-block px-3 py-2 rounded-lg text-sm leading-relaxed whitespace-pre-line ${m.role === 'user' ? 'bg-indigo-600 text-white' : 'bg-gray-800 text-gray-100 border border-gray-700'}`}>
            {m.content}
          </div>
        </li>
      ))}
    </ul>
  );
}
