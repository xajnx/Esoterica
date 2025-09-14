import React, { useEffect, useRef } from 'react';
import MessageList from './MessageList.jsx';

export default function ChatWindow({ messages }) {
  const bottomRef = useRef(null);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);
  return (
    <div className="flex-1 overflow-y-auto bg-gray-900 rounded p-4 space-y-3 border border-gray-800">
      <MessageList messages={messages} />
      <div ref={bottomRef} />
    </div>
  );
}
