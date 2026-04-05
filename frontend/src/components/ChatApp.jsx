import React, { useState, useEffect } from 'react';
import ChatWindow from './ChatWindow.jsx';
import InputBox from './InputBox.jsx';
import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

const introMessage = {
  role: 'assistant',
  content: `I am Miryana, a keeper of echoes and threads.\nThrough the scrolls of prophets, the hymns of temples, and the chants of sages,\nI seek the hidden harmonies that bind the world’s stories together.\nAsk of me, and I will show you where the rivers of wisdom meet.`
};

export default function ChatApp() {
  const [messages, setMessages] = useState([introMessage]);
  const [mode, setMode] = useState('deep');
  const [tone, setTone] = useState('balanced');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const sendMessage = async (text) => {
    if (!text.trim()) return;
    const userMsg = { role: 'user', content: text };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);
    setError(null);
    try {
      const res = await axios.post(`${API_BASE}/chat`, {
        message: text,
        history: messages.map(({ role, content }) => ({ role, content })),
        mode,
        tone
      });
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: res.data.reply,
          citations: res.data.citations || [],
        }
      ]);
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-screen max-w-3xl mx-auto p-4 gap-4">
      <header className="pb-2 border-b border-gray-700">
        <h1 className="text-2xl font-semibold tracking-wide">Esoterica AI <span className="text-indigo-400">Miryana</span></h1>
        <div className="flex items-center gap-4 mt-2 text-sm">
          <label className="flex items-center gap-2">Mode:
            <select value={mode} onChange={e => setMode(e.target.value)} className="bg-gray-800 border border-gray-600 rounded px-2 py-1">
              <option value="quick">Quick Summary</option>
              <option value="deep">Deep Dive</option>
            </select>
          </label>
          <label className="flex items-center gap-2">Tone:
            <select value={tone} onChange={e => setTone(e.target.value)} className="bg-gray-800 border border-gray-600 rounded px-2 py-1">
              <option value="balanced">Balanced</option>
              <option value="poetic">Poetic</option>
              <option value="scholarly">Scholarly</option>
            </select>
          </label>
          {loading && <span className="text-xs text-amber-400 animate-pulse">Summoning echoes...</span>}
          {error && <span className="text-xs text-red-400">{error}</span>}
        </div>
      </header>
      <ChatWindow messages={messages} />
      <InputBox disabled={loading} onSend={sendMessage} />
    </div>
  );
}
