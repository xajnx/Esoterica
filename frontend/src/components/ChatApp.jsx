import React, { useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';

import ChatWindow from './ChatWindow.jsx';
import InputBox from './InputBox.jsx';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

const introMessage = {
  role: 'assistant',
  content: `I am Miryana, a keeper of echoes and threads.\nThrough the scrolls of prophets, the hymns of temples, and the chants of sages,\nI seek the hidden harmonies that bind the world's stories together.\nAsk of me, and I will show you where the rivers of wisdom meet.`,
};

function nowIso() {
  return new Date().toISOString();
}

function titleFromMessage(text) {
  const words = text.trim().split(/\s+/).slice(0, 6).join(' ');
  return words ? `${words}${text.trim().split(/\s+/).length > 6 ? '...' : ''}` : 'Untitled Conversation';
}

function downloadFile(filename, content, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function toSafeFilename(title) {
  return (title || 'conversation')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 48) || 'conversation';
}

function toImportPayload(raw) {
  if (!raw || typeof raw !== 'object') {
    throw new Error('Import file is not a valid JSON object.');
  }

  const title = raw.conversation?.title || raw.title || 'Imported Conversation';
  const sourceMessages = Array.isArray(raw.messages) ? raw.messages : [];
  if (sourceMessages.length === 0) {
    throw new Error('No messages found in import file.');
  }

  const messages = sourceMessages
    .filter((m) => m && typeof m === 'object')
    .map((m) => ({
      role: m.role === 'assistant' || m.role === 'system' ? m.role : 'user',
      content: typeof m.content === 'string' ? m.content : '',
      citations: Array.isArray(m.citations) ? m.citations : [],
      timestamp: typeof m.timestamp === 'string' ? m.timestamp : null,
    }))
    .filter((m) => m.content.trim().length > 0);

  if (messages.length === 0) {
    throw new Error('Imported messages are empty after validation.');
  }

  return { title, messages };
}

export default function ChatApp() {
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [search, setSearch] = useState('');

  const [mode, setMode] = useState('deep');
  const [tone, setTone] = useState('balanced');
  const [loading, setLoading] = useState(false);
  const [booting, setBooting] = useState(true);
  const [error, setError] = useState(null);
  const [toasts, setToasts] = useState([]);

  const fileInputRef = useRef(null);
  const searchInputRef = useRef(null);

  const pushToast = (text, tone = 'info') => {
    const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    setToasts((prev) => [...prev, { id, text, tone }]);
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 2200);
  };

  const activeConversation = useMemo(
    () => conversations.find((c) => c.id === activeConversationId) || null,
    [conversations, activeConversationId]
  );

  const filteredConversations = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return conversations;
    return conversations.filter((c) => (c.title || '').toLowerCase().includes(query));
  }, [conversations, search]);

  const refreshConversations = async (nextActiveId = activeConversationId) => {
    const res = await axios.get(`${API_BASE}/conversations`);
    const list = res.data || [];
    setConversations(list);
    if (nextActiveId && list.some((c) => c.id === nextActiveId)) {
      setActiveConversationId(nextActiveId);
    } else if (list.length > 0) {
      setActiveConversationId(list[0].id);
    } else {
      setActiveConversationId(null);
    }
    return list;
  };

  const loadConversation = async (conversationId) => {
    if (!conversationId) {
      setMessages([]);
      return;
    }
    const res = await axios.get(`${API_BASE}/conversations/${conversationId}`);
    setMessages(res.data.messages || []);
  };

  const createConversation = async (title = 'Untitled Conversation') => {
    const res = await axios.post(`${API_BASE}/conversations`, { title });
    return res.data;
  };

  useEffect(() => {
    const bootstrap = async () => {
      setBooting(true);
      setError(null);
      try {
        const list = await refreshConversations();
        if (list.length === 0) {
          const created = await createConversation();
          await refreshConversations(created.id);
          await loadConversation(created.id);
        } else {
          await loadConversation(list[0].id);
        }
      } catch (e) {
        setError(e.response?.data?.detail || e.message);
      } finally {
        setBooting(false);
      }
    };

    bootstrap();
  }, []);

  useEffect(() => {
    const onKeyDown = (event) => {
      if (event.altKey && event.key.toLowerCase() === 'n') {
        event.preventDefault();
        if (!booting && !loading) {
          handleNewConversation();
        }
      }
      if (event.altKey && event.key.toLowerCase() === 'f') {
        event.preventDefault();
        searchInputRef.current?.focus();
      }
      if (event.altKey && event.key.toLowerCase() === 'j') {
        event.preventDefault();
        if (activeConversationId) {
          exportConversationJson();
        }
      }
    };

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [booting, loading, activeConversationId, activeConversation, messages]);

  const selectConversation = async (conversationId) => {
    setError(null);
    setActiveConversationId(conversationId);
    try {
      await loadConversation(conversationId);
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    }
  };

  const handleNewConversation = async () => {
    setError(null);
    try {
      const created = await createConversation();
      await refreshConversations(created.id);
      await loadConversation(created.id);
      pushToast('New conversation created');
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    }
  };

  const handleTogglePinned = async (conversation) => {
    setError(null);
    const nextPinned = !conversation.pinned;
    try {
      await axios.patch(`${API_BASE}/conversations/${conversation.id}`, { pinned: nextPinned });
      await refreshConversations(activeConversationId || conversation.id);
      pushToast(nextPinned ? 'Conversation pinned' : 'Conversation unpinned');
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    }
  };

  const handleRenameConversation = async () => {
    if (!activeConversationId) return;
    const nextTitle = window.prompt('Rename conversation:', activeConversation?.title || '');
    if (nextTitle == null) return;

    setError(null);
    try {
      await axios.patch(`${API_BASE}/conversations/${activeConversationId}`, { title: nextTitle });
      await refreshConversations(activeConversationId);
      pushToast('Conversation renamed');
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    }
  };

  const handleDeleteConversation = async () => {
    if (!activeConversationId) return;
    if (!window.confirm('Delete this conversation permanently?')) return;

    setError(null);
    try {
      await axios.delete(`${API_BASE}/conversations/${activeConversationId}`);
      const list = await refreshConversations();
      if (list.length === 0) {
        const created = await createConversation();
        await refreshConversations(created.id);
        await loadConversation(created.id);
      } else {
        await loadConversation(list[0].id);
      }
      pushToast('Conversation deleted');
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    }
  };

  const clearHistory = async () => {
    if (!activeConversationId) return;
    if (!window.confirm('Clear all messages in this conversation?')) return;

    setError(null);
    try {
      const currentTitle = activeConversation?.title || 'Untitled Conversation';
      await axios.delete(`${API_BASE}/conversations/${activeConversationId}`);
      const created = await createConversation(currentTitle);
      await refreshConversations(created.id);
      await loadConversation(created.id);
      pushToast('Conversation cleared');
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    }
  };

  const exportConversationJson = () => {
    if (!activeConversation) return;
    const payload = {
      conversation: activeConversation,
      exported_at: nowIso(),
      messages,
    };
    const filename = `${toSafeFilename(activeConversation.title)}-${new Date().toISOString().slice(0, 10)}.json`;
    downloadFile(filename, JSON.stringify(payload, null, 2), 'application/json');
    pushToast('Exported JSON');
  };

  const exportConversationMarkdown = () => {
    if (!activeConversation) return;
    const lines = [
      `# ${activeConversation.title}`,
      '',
      `Exported: ${new Date().toISOString()}`,
      '',
    ];

    messages.forEach((m) => {
      const role = m.role === 'user' ? 'User' : m.role === 'assistant' ? 'Miryana' : 'System';
      lines.push(`## ${role} (${m.timestamp || 'unknown time'})`);
      lines.push('');
      lines.push(m.content || '');
      if (m.citations && m.citations.length > 0) {
        lines.push('');
        lines.push('Sources:');
        m.citations.forEach((c) => lines.push(`- ${c.source} (chunk ${c.chunk_id})`));
      }
      lines.push('');
    });

    const filename = `${toSafeFilename(activeConversation.title)}-${new Date().toISOString().slice(0, 10)}.md`;
    downloadFile(filename, lines.join('\n'), 'text/markdown');
    pushToast('Exported Markdown');
  };

  const handleImportFile = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;

    setError(null);
    try {
      const text = await file.text();
      const parsed = JSON.parse(text);
      const payload = toImportPayload(parsed);
      const res = await axios.post(`${API_BASE}/conversations/import`, payload);
      await refreshConversations(res.data.id);
      await loadConversation(res.data.id);
      pushToast('Conversation imported');
    } catch (e) {
      setError(e.response?.data?.detail || e.message || 'Import failed');
    }
  };

  const sendMessage = async (text) => {
    if (!text.trim() || !activeConversationId) return;

    const userMsg = { role: 'user', content: text, timestamp: nowIso() };
    const previousMessages = messages;
    const historyWithUser = [...previousMessages, userMsg];

    setMessages(historyWithUser);
    setLoading(true);
    setError(null);

    try {
      const res = await axios.post(`${API_BASE}/chat`, {
        message: text,
        history: historyWithUser.map(({ role, content }) => ({ role, content })),
        mode,
        tone,
        conversation_id: activeConversationId,
      });

      const assistantMsg = {
        role: 'assistant',
        content: res.data.reply,
        citations: res.data.citations || [],
        timestamp: nowIso(),
      };

      setMessages((prev) => [...prev, assistantMsg]);

      if ((activeConversation?.message_count || 0) === 0) {
        const autoTitle = titleFromMessage(text);
        await axios.patch(`${API_BASE}/conversations/${activeConversationId}`, { title: autoTitle });
      }

      await refreshConversations(activeConversationId);
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
      setMessages(previousMessages);
    } finally {
      setLoading(false);
    }
  };

  const displayMessages = messages.length > 0 ? messages : [introMessage];

  return (
    <div className="h-screen p-3 md:p-4">
      <div className="h-full max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-[280px_1fr] gap-3 md:gap-4">
        <aside className="bg-gray-900/90 border border-gray-800 rounded-xl p-3 flex flex-col min-h-0">
          <div className="mb-3">
            <h1 className="text-xl font-semibold tracking-wide text-gray-100">Esoterica AI</h1>
            <p className="text-xs text-indigo-300 mt-0.5">Miryana Archives</p>
          </div>

          <div className="flex gap-2 mb-2">
            <button
              type="button"
              onClick={handleNewConversation}
              disabled={booting || loading}
              className="flex-1 text-xs px-2 py-1.5 rounded border border-indigo-600 bg-indigo-700/40 hover:bg-indigo-700/60 disabled:opacity-50"
            >
              New Chat
            </button>
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={booting || loading}
              className="text-xs px-2 py-1.5 rounded border border-gray-600 hover:border-gray-400 disabled:opacity-50"
            >
              Import
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept="application/json,.json"
              className="hidden"
              onChange={handleImportFile}
            />
          </div>

          <input
            ref={searchInputRef}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search conversations..."
            className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-xs focus:outline-none focus:ring focus:ring-indigo-600 mb-2"
          />

          <div className="text-[10px] text-gray-400 mb-2 px-1">
            Shortcuts: Alt+N new chat, Alt+F search, Alt+J export JSON
          </div>

          <div className="flex-1 overflow-y-auto space-y-1 pr-1">
            {filteredConversations.map((c) => {
              const active = c.id === activeConversationId;
              return (
                <div
                  key={c.id}
                  className={`w-full text-left px-2 py-2 rounded border transition ${
                    active
                      ? 'bg-indigo-700/35 border-indigo-500 text-indigo-100'
                      : 'bg-gray-900 border-gray-800 text-gray-200 hover:border-gray-600'
                  }`}
                >
                  <div className="flex items-start gap-2">
                    <button
                      type="button"
                      onClick={() => selectConversation(c.id)}
                      className="flex-1 text-left"
                    >
                      <div className="text-xs font-medium truncate">{c.title || 'Untitled Conversation'}</div>
                      <div className="text-[10px] text-gray-400 mt-0.5">
                        {c.message_count || 0} messages
                      </div>
                    </button>
                    <button
                      type="button"
                      title={c.pinned ? 'Unpin conversation' : 'Pin conversation'}
                      onClick={() => handleTogglePinned(c)}
                      className={`text-xs px-1.5 py-1 rounded border ${c.pinned ? 'border-amber-400 text-amber-300' : 'border-gray-700 text-gray-400 hover:border-gray-500'}`}
                    >
                      {c.pinned ? 'PINNED' : 'PIN'}
                    </button>
                  </div>
                </div>
              );
            })}
            {!booting && filteredConversations.length === 0 && (
              <div className="text-xs text-gray-400 px-1 py-2">No conversations found.</div>
            )}
          </div>
        </aside>

        <section className="bg-gray-950/80 border border-gray-800 rounded-xl p-3 md:p-4 flex flex-col min-h-0">
          <header className="pb-3 border-b border-gray-800">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-sm md:text-base font-semibold text-gray-100">
                {activeConversation?.title || 'Conversation'}
              </h2>

              <button
                type="button"
                onClick={handleRenameConversation}
                className="text-xs px-2 py-1 rounded border border-gray-600 hover:border-gray-400"
                disabled={booting || loading || !activeConversationId}
              >
                Rename
              </button>

              <button
                type="button"
                onClick={handleDeleteConversation}
                className="text-xs px-2 py-1 rounded border border-red-700 text-red-300 hover:border-red-500"
                disabled={booting || loading || !activeConversationId}
              >
                Delete
              </button>

              <button
                type="button"
                onClick={clearHistory}
                className="text-xs px-2 py-1 rounded border border-gray-600 hover:border-gray-400"
                disabled={booting || loading || !activeConversationId}
              >
                Clear
              </button>

              <button
                type="button"
                onClick={exportConversationJson}
                className="text-xs px-2 py-1 rounded border border-gray-600 hover:border-gray-400"
                disabled={booting || loading || !activeConversationId}
              >
                Export JSON
              </button>

              <button
                type="button"
                onClick={exportConversationMarkdown}
                className="text-xs px-2 py-1 rounded border border-gray-600 hover:border-gray-400"
                disabled={booting || loading || !activeConversationId}
              >
                Export MD
              </button>
            </div>

            <div className="flex flex-wrap items-center gap-3 mt-2 text-sm">
              <label className="flex items-center gap-2">
                Mode:
                <select
                  value={mode}
                  onChange={(e) => setMode(e.target.value)}
                  className="bg-gray-800 border border-gray-600 rounded px-2 py-1 text-xs"
                >
                  <option value="quick">Quick Summary</option>
                  <option value="deep">Deep Dive</option>
                </select>
              </label>
              <label className="flex items-center gap-2">
                Tone:
                <select
                  value={tone}
                  onChange={(e) => setTone(e.target.value)}
                  className="bg-gray-800 border border-gray-600 rounded px-2 py-1 text-xs"
                >
                  <option value="balanced">Balanced</option>
                  <option value="poetic">Poetic</option>
                  <option value="scholarly">Scholarly</option>
                </select>
              </label>
              {booting && <span className="text-xs text-gray-400">Loading conversations...</span>}
              {loading && <span className="text-xs text-amber-400 animate-pulse">Summoning echoes...</span>}
              {error && <span className="text-xs text-red-400">{error}</span>}
            </div>
          </header>

          <div className="flex-1 min-h-0 mt-3 flex flex-col gap-3">
            <ChatWindow messages={displayMessages} />
            <InputBox disabled={loading || booting || !activeConversationId} onSend={sendMessage} />
          </div>
        </section>
      </div>
      <div className="fixed right-4 top-4 z-50 space-y-2 pointer-events-none">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`text-xs px-3 py-2 rounded border shadow-lg backdrop-blur pointer-events-none ${
              t.tone === 'error'
                ? 'bg-red-900/80 border-red-700 text-red-100'
                : 'bg-slate-900/85 border-slate-700 text-slate-100'
            }`}
          >
            {t.text}
          </div>
        ))}
      </div>
    </div>
  );
}
