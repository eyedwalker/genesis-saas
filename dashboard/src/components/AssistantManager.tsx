"use client";

import { useEffect, useState } from "react";
import {
  listAssistants,
  getAssistant,
  createAssistant,
  updateAssistant,
  forkAssistant,
  deleteAssistant,
  type AssistantSummary,
  type AssistantDetail,
} from "@/lib/api";

const DOMAIN_ICONS: Record<string, string> = {
  quality: "🔍", architecture: "🏗️", compliance: "🛡️", infrastructure: "⚙️",
  frontend: "🎨", design: "✨", business: "📈", project: "🧭", ba: "📋",
};

// ── Editor Modal ─────────────────────────────────────────────────────────────

function AssistantEditor({
  assistant,
  domains,
  onSave,
  onClose,
}: {
  assistant: AssistantDetail | null; // null = create new
  domains: Record<string, string>;
  onSave: () => void;
  onClose: () => void;
}) {
  const isNew = !assistant || assistant.source === "catalog";
  const [name, setName] = useState(assistant?.name || "");
  const [domain, setDomain] = useState(assistant?.domain || "quality");
  const [description, setDescription] = useState(assistant?.description || "");
  const [systemPrompt, setSystemPrompt] = useState(assistant?.system_prompt || "");
  const [weight, setWeight] = useState(assistant?.weight || 1.0);
  const [isActive, setIsActive] = useState(assistant?.is_active ?? true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const handleSave = async () => {
    if (!name.trim() || !systemPrompt.trim()) {
      setError("Name and system prompt are required");
      return;
    }
    setSaving(true);
    setError("");
    try {
      if (assistant && assistant.source === "custom") {
        await updateAssistant(assistant.id, {
          name, domain, description, system_prompt: systemPrompt, weight, is_active: isActive,
        });
      } else {
        await createAssistant({
          name, domain, description, system_prompt: systemPrompt, weight, is_active: isActive,
        });
      }
      onSave();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[90vh] flex flex-col">
        <div className="px-6 py-4 border-b">
          <h2 className="text-xl font-semibold">
            {assistant?.source === "custom" ? "Edit Assistant" : "Create Assistant"}
          </h2>
          {assistant?.source === "catalog" && (
            <p className="text-sm text-amber-600 mt-1">
              This is a catalog assistant — saving will create a custom copy
            </p>
          )}
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
              <input
                value={name} onChange={(e) => setName(e.target.value)}
                className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-genesis-500 focus:outline-none"
                placeholder="e.g. HIPAA Compliance Reviewer"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Domain</label>
              <select
                value={domain} onChange={(e) => setDomain(e.target.value)}
                className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-genesis-500 focus:outline-none"
              >
                {Object.entries(domains).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
            <input
              value={description} onChange={(e) => setDescription(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-genesis-500 focus:outline-none"
              placeholder="Brief description of what this assistant reviews/guides"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              System Prompt
              <span className="text-gray-400 font-normal ml-2">
                ({systemPrompt.length} chars)
              </span>
            </label>
            <textarea
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              rows={16}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-genesis-500 focus:outline-none font-mono text-sm resize-y"
              placeholder="You are an expert reviewer who specializes in..."
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Weight <span className="text-gray-400 font-normal">(scoring multiplier)</span>
              </label>
              <input
                type="number" step="0.5" min="0.5" max="5.0"
                value={weight} onChange={(e) => setWeight(parseFloat(e.target.value))}
                className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-genesis-500 focus:outline-none"
              />
              <p className="text-xs text-gray-400 mt-1">
                1.0 = normal, 2.0 = issues weighted 2x, 3.0 = critical domain
              </p>
            </div>
            <div className="flex items-end pb-2">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox" checked={isActive}
                  onChange={(e) => setIsActive(e.target.checked)}
                  className="rounded"
                />
                <span className="text-sm text-gray-700">Active</span>
              </label>
            </div>
          </div>

          {error && <p className="text-red-500 text-sm">{error}</p>}
        </div>

        <div className="px-6 py-4 border-t bg-gray-50 flex justify-end gap-3">
          <button onClick={onClose}
            className="px-4 py-2 border rounded-lg text-gray-600 hover:bg-white transition">
            Cancel
          </button>
          <button onClick={handleSave} disabled={saving}
            className="px-6 py-2 bg-genesis-600 text-white rounded-lg hover:bg-genesis-700 disabled:opacity-50 transition font-medium">
            {saving ? "Saving..." : "Save Assistant"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main Component ───────────────────────────────────────────────────────────

export function AssistantManager({ onBack }: { onBack: () => void }) {
  const [assistants, setAssistants] = useState<AssistantSummary[]>([]);
  const [domains, setDomains] = useState<Record<string, string>>({});
  const [filterDomain, setFilterDomain] = useState<string>("");
  const [filterSource, setFilterSource] = useState<string>("");
  const [selectedDetail, setSelectedDetail] = useState<AssistantDetail | null>(null);
  const [showEditor, setShowEditor] = useState(false);
  const [editorAssistant, setEditorAssistant] = useState<AssistantDetail | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    const res = await listAssistants(filterDomain || undefined, filterSource || undefined);
    setAssistants(res.assistants);
    setDomains(res.domains);
    setLoading(false);
  };

  useEffect(() => { refresh(); }, [filterDomain, filterSource]);

  const handleView = async (id: string) => {
    const detail = await getAssistant(id);
    setSelectedDetail(detail);
  };

  const handleEdit = async (id: string) => {
    const detail = await getAssistant(id);
    setEditorAssistant(detail);
    setShowEditor(true);
  };

  const handleFork = async (id: string) => {
    try {
      const forked = await forkAssistant(id);
      setEditorAssistant(forked);
      setShowEditor(true);
      refresh();
    } catch (err: any) {
      console.error(err.message);
    }
  };

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`Delete "${name}"? This cannot be undone.`)) return;
    try {
      await deleteAssistant(id);
      refresh();
      if (selectedDetail?.id === id) setSelectedDetail(null);
    } catch (err: any) {
      console.error(err.message);
    }
  };

  const handleCreate = () => {
    setEditorAssistant(null);
    setShowEditor(true);
  };

  // Group by domain
  const grouped: Record<string, AssistantSummary[]> = {};
  for (const a of assistants) {
    if (!grouped[a.domain]) grouped[a.domain] = [];
    grouped[a.domain].push(a);
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <button onClick={onBack} className="text-gray-400 hover:text-gray-600 text-sm">
            ← Back
          </button>
          <h2 className="text-2xl font-semibold text-gray-900">Assistants</h2>
          <span className="text-sm text-gray-500">{assistants.length} total</span>
        </div>
        <button onClick={handleCreate}
          className="px-4 py-2 bg-genesis-600 text-white rounded-lg hover:bg-genesis-700 transition text-sm font-medium">
          + New Assistant
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-6">
        <select value={filterDomain} onChange={(e) => setFilterDomain(e.target.value)}
          className="px-3 py-2 border rounded-lg text-sm">
          <option value="">All Domains</option>
          {Object.entries(domains).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
        <select value={filterSource} onChange={(e) => setFilterSource(e.target.value)}
          className="px-3 py-2 border rounded-lg text-sm">
          <option value="">All Sources</option>
          <option value="catalog">Catalog (built-in)</option>
          <option value="custom">Custom (yours)</option>
        </select>
      </div>

      <div className="flex gap-6">
        {/* Left: List */}
        <div className="flex-1 space-y-6">
          {Object.entries(grouped).map(([domain, items]) => (
            <div key={domain}>
              <h3 className="text-sm font-semibold text-gray-600 mb-2">
                {DOMAIN_ICONS[domain] || "📦"} {domains[domain] || domain}
                <span className="text-gray-400 font-normal ml-2">({items.length})</span>
              </h3>
              <div className="space-y-2">
                {items.map((a) => (
                  <div
                    key={a.id}
                    className={`p-3 rounded-lg border cursor-pointer transition ${
                      selectedDetail?.id === a.id
                        ? "border-genesis-400 bg-genesis-50 ring-1 ring-genesis-300"
                        : "bg-white hover:border-gray-300"
                    }`}
                    onClick={() => handleView(a.id)}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-gray-800">
                            {a.name}
                          </span>
                          <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                            a.source === "custom"
                              ? "bg-purple-100 text-purple-700"
                              : "bg-gray-100 text-gray-500"
                          }`}>
                            {a.source}
                          </span>
                          {a.weight > 1.5 && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-700">
                              {a.weight}x
                            </span>
                          )}
                          {!a.is_active && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-500">
                              disabled
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-gray-500 mt-0.5 truncate">
                          {a.description}
                        </p>
                      </div>
                      <div className="flex items-center gap-1 ml-2">
                        {a.source === "catalog" ? (
                          <button
                            onClick={(e) => { e.stopPropagation(); handleFork(a.id); }}
                            className="text-xs px-2 py-1 text-genesis-600 hover:bg-genesis-50 rounded"
                            title="Fork to customize"
                          >
                            Fork
                          </button>
                        ) : (
                          <>
                            <button
                              onClick={(e) => { e.stopPropagation(); handleEdit(a.id); }}
                              className="text-xs px-2 py-1 text-genesis-600 hover:bg-genesis-50 rounded"
                            >
                              Edit
                            </button>
                            <button
                              onClick={(e) => { e.stopPropagation(); handleDelete(a.id, a.name); }}
                              className="text-xs px-2 py-1 text-red-500 hover:bg-red-50 rounded"
                            >
                              Delete
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Right: Detail panel */}
        <div className="w-96 flex-shrink-0">
          {selectedDetail ? (
            <div className="bg-white border rounded-xl p-5 sticky top-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold text-gray-900">{selectedDetail.name}</h3>
                <span className={`text-xs px-2 py-0.5 rounded ${
                  selectedDetail.source === "custom"
                    ? "bg-purple-100 text-purple-700"
                    : "bg-gray-100 text-gray-500"
                }`}>
                  {selectedDetail.source}
                </span>
              </div>
              <p className="text-sm text-gray-600 mb-3">{selectedDetail.description}</p>
              <div className="flex gap-4 text-xs text-gray-500 mb-4">
                <span>Domain: {selectedDetail.domain_label}</span>
                <span>Weight: {selectedDetail.weight}x</span>
                <span>{selectedDetail.is_active ? "Active" : "Disabled"}</span>
              </div>
              <div className="border-t pt-3">
                <h4 className="text-xs font-semibold text-gray-600 mb-2">
                  System Prompt ({selectedDetail.system_prompt.length} chars)
                </h4>
                <pre className="text-xs text-gray-700 whitespace-pre-wrap bg-gray-50 rounded-lg p-3 max-h-96 overflow-y-auto font-mono">
                  {selectedDetail.system_prompt}
                </pre>
              </div>
              <div className="mt-4 flex gap-2">
                {selectedDetail.source === "catalog" ? (
                  <button onClick={() => handleFork(selectedDetail.id)}
                    className="flex-1 py-2 text-sm border rounded-lg text-genesis-600 hover:bg-genesis-50 transition">
                    Fork & Customize
                  </button>
                ) : (
                  <>
                    <button onClick={() => handleEdit(selectedDetail.id)}
                      className="flex-1 py-2 text-sm bg-genesis-600 text-white rounded-lg hover:bg-genesis-700 transition">
                      Edit
                    </button>
                    <button onClick={() => handleDelete(selectedDetail.id, selectedDetail.name)}
                      className="py-2 px-4 text-sm border border-red-200 text-red-600 rounded-lg hover:bg-red-50 transition">
                      Delete
                    </button>
                  </>
                )}
              </div>
            </div>
          ) : (
            <div className="bg-white border rounded-xl p-8 text-center text-gray-400">
              <p className="text-lg mb-1">Select an assistant</p>
              <p className="text-sm">Click any assistant to view its system prompt and details</p>
            </div>
          )}
        </div>
      </div>

      {/* Editor modal */}
      {showEditor && (
        <AssistantEditor
          assistant={editorAssistant}
          domains={domains}
          onSave={() => { setShowEditor(false); refresh(); }}
          onClose={() => setShowEditor(false)}
        />
      )}
    </div>
  );
}
