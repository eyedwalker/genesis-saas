"use client";

import { useEffect, useRef, useState } from "react";
import {
  sendMessage,
  scanWebsite,
  getConversation,
  generateRequirements,
  type ConversationState,
  type ConversationMessage,
} from "@/lib/api";
import { DiscoveryBoard } from "./DiscoveryBoard";

function MessageBubble({ msg }: { msg: ConversationMessage }) {
  const isUser = msg.role === "user";
  const isSystem = msg.role === "system";

  if (isSystem) {
    return (
      <div className="flex justify-center my-3">
        <div className="bg-blue-50 text-blue-700 text-xs px-4 py-2 rounded-full max-w-lg text-center">
          {msg.content}
        </div>
      </div>
    );
  }

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      <div
        className={`max-w-[75%] rounded-2xl px-4 py-3 ${
          isUser
            ? "bg-genesis-600 text-white rounded-br-md"
            : "bg-white border text-gray-800 rounded-bl-md shadow-sm"
        }`}
      >
        {!isUser && (
          <div className="text-xs text-genesis-600 font-medium mb-1">
            Genesis
          </div>
        )}
        <div className="text-sm whitespace-pre-wrap">{msg.content}</div>
        {msg.attachments && msg.attachments.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {msg.attachments.map((a, i) => (
              <span
                key={i}
                className={`text-xs px-2 py-1 rounded ${
                  isUser ? "bg-white/20" : "bg-gray-100"
                }`}
              >
                {a.name}
              </span>
            ))}
          </div>
        )}
        <div
          className={`text-[10px] mt-1 ${
            isUser ? "text-white/60" : "text-gray-400"
          }`}
        >
          {new Date(msg.timestamp).toLocaleTimeString()}
        </div>
      </div>
    </div>
  );
}

export function ConversationView({
  buildId,
  initialState,
  onRequirementsGenerated,
  onBack,
}: {
  buildId: string;
  initialState: ConversationState;
  onRequirementsGenerated: (buildId: string) => void;
  onBack: () => void;
}) {
  const [state, setState] = useState<ConversationState>(initialState);
  const [input, setInput] = useState("");
  const [urlInput, setUrlInput] = useState("");
  const [sending, setSending] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [showUrlInput, setShowUrlInput] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [state.messages]);

  const handleSend = async () => {
    if (!input.trim() || sending) return;
    const msg = input;
    setInput("");
    setSending(true);

    // Optimistic: add user message immediately
    setState((prev) => ({
      ...prev,
      messages: [
        ...prev.messages,
        { role: "user", content: msg, timestamp: new Date().toISOString() },
      ],
    }));

    try {
      const updated = await sendMessage(buildId, msg);
      setState(updated);
    } catch (err: any) {
      console.error(err.message);
    } finally {
      setSending(false);
    }
  };

  const handleScanUrl = async () => {
    if (!urlInput.trim() || scanning) return;
    const url = urlInput;
    setUrlInput("");
    setShowUrlInput(false);
    setScanning(true);

    try {
      const updated = await scanWebsite(buildId, url);
      setState(updated);
    } catch (err: any) {
      console.error(`Scan failed: ${err.message}`);
    } finally {
      setScanning(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async () => {
      const content =
        typeof reader.result === "string"
          ? reader.result
          : `[Binary file: ${file.name}]`;

      setSending(true);
      try {
        const updated = await sendMessage(buildId, `I'm sharing a file: ${file.name}`, [
          { type: file.type, name: file.name, content: content.slice(0, 5000) },
        ]);
        setState(updated);
      } catch (err: any) {
        console.error(err.message);
      } finally {
        setSending(false);
      }
    };
    reader.readAsText(file);
  };

  const handleGenerateRequirements = async () => {
    setGenerating(true);
    try {
      await generateRequirements(buildId);
      onRequirementsGenerated(buildId);
    } catch (err: any) {
      console.error(err.message);
    } finally {
      setGenerating(false);
    }
  };

  const uploads = state.context?.uploads || [];
  const scans = state.context?.scans || [];

  return (
    <div className="flex h-[calc(100vh-120px)]">
    {/* Main conversation */}
    <div className="flex flex-col flex-1">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b bg-white">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="text-gray-400 hover:text-gray-600 text-sm"
          >
            ← Back
          </button>
          <div>
            <h2 className="font-semibold text-gray-900">Discovery</h2>
            <p className="text-xs text-gray-500">
              {state.messages.length} messages
              {uploads.length > 0 && ` · ${uploads.length} files`}
              {scans.length > 0 && ` · ${scans.length} sites scanned`}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {state.ready_to_build && (
            <button
              onClick={handleGenerateRequirements}
              disabled={generating}
              className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50 transition"
            >
              {generating ? "Generating..." : "Generate Requirements →"}
            </button>
          )}
        </div>
      </div>

      {/* Context bar (uploads + scans) */}
      {(uploads.length > 0 || scans.length > 0) && (
        <div className="px-4 py-2 bg-gray-50 border-b flex flex-wrap gap-2">
          {uploads.map((u: any, i: number) => (
            <span
              key={`u-${i}`}
              className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded-full"
            >
              {u.name}
            </span>
          ))}
          {scans.map((s: any, i: number) => (
            <span
              key={`s-${i}`}
              className="text-xs bg-purple-100 text-purple-700 px-2 py-1 rounded-full"
            >
              {new URL(s.url).hostname}
            </span>
          ))}
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 bg-gray-50">
        {state.messages.map((msg, i) => (
          <MessageBubble key={i} msg={msg} />
        ))}
        {(sending || scanning) && (
          <div className="flex justify-start mb-4">
            <div className="bg-white border rounded-2xl rounded-bl-md px-4 py-3 shadow-sm">
              <div className="flex items-center gap-2 text-sm text-gray-400">
                <div className="animate-pulse">
                  {scanning ? "Scanning website..." : "Thinking..."}
                </div>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* URL input (toggled) */}
      {showUrlInput && (
        <div className="px-4 py-2 bg-purple-50 border-t flex gap-2">
          <input
            type="url"
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            placeholder="https://example.com — paste a website to scan"
            className="flex-1 px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-purple-400 focus:outline-none"
            onKeyDown={(e) => e.key === "Enter" && handleScanUrl()}
          />
          <button
            onClick={handleScanUrl}
            disabled={!urlInput.trim() || scanning}
            className="px-3 py-2 bg-purple-600 text-white rounded-lg text-sm hover:bg-purple-700 disabled:opacity-50"
          >
            Scan
          </button>
          <button
            onClick={() => setShowUrlInput(false)}
            className="px-2 text-gray-400 hover:text-gray-600"
          >
            ✕
          </button>
        </div>
      )}

      {/* Input bar */}
      <div className="px-4 py-3 bg-white border-t">
        <div className="flex items-center gap-2">
          {/* Attach button */}
          <button
            onClick={() => fileInputRef.current?.click()}
            className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition"
            title="Upload document or image"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
            </svg>
          </button>
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            onChange={handleFileUpload}
            accept=".txt,.md,.pdf,.csv,.json,.png,.jpg,.jpeg,.gif,.docx,.xlsx"
          />

          {/* Scan URL button */}
          <button
            onClick={() => setShowUrlInput(!showUrlInput)}
            className={`p-2 rounded-lg transition ${
              showUrlInput
                ? "text-purple-600 bg-purple-50"
                : "text-gray-400 hover:text-gray-600 hover:bg-gray-100"
            }`}
            title="Scan a website"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
            </svg>
          </button>

          {/* Text input */}
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Describe what you want to build..."
            className="flex-1 px-4 py-2.5 border rounded-xl text-sm focus:ring-2 focus:ring-genesis-500 focus:outline-none"
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
            disabled={sending}
          />

          {/* Send button */}
          <button
            onClick={handleSend}
            disabled={!input.trim() || sending}
            className="p-2.5 bg-genesis-600 text-white rounded-xl hover:bg-genesis-700 disabled:opacity-50 transition"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
          </button>
        </div>
      </div>
    </div>

    {/* Discovery Board sidebar */}
    <DiscoveryBoard state={state} />
    </div>
  );
}
