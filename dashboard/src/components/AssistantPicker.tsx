"use client";

import { useEffect, useState } from "react";
import { listAssistants, type AssistantSummary } from "@/lib/api";

const DOMAIN_ICONS: Record<string, string> = {
  quality: "🔍",
  architecture: "🏗️",
  compliance: "🛡️",
  infrastructure: "⚙️",
  frontend: "🎨",
  design: "✨",
  business: "📈",
  project: "🧭",
  ba: "📋",
};

const DOMAIN_COLORS: Record<string, string> = {
  quality: "border-blue-200 bg-blue-50",
  architecture: "border-indigo-200 bg-indigo-50",
  compliance: "border-red-200 bg-red-50",
  infrastructure: "border-gray-200 bg-gray-50",
  frontend: "border-purple-200 bg-purple-50",
  design: "border-pink-200 bg-pink-50",
  business: "border-amber-200 bg-amber-50",
  project: "border-green-200 bg-green-50",
  ba: "border-teal-200 bg-teal-50",
};

export function AssistantPicker({
  onStart,
  onCancel,
  factoryId,
  initialIdea,
}: {
  onStart: (assistantIds: string[]) => void;
  onCancel: () => void;
  factoryId: string;
  initialIdea: string;
}) {
  const [assistants, setAssistants] = useState<AssistantSummary[]>([]);
  const [domains, setDomains] = useState<Record<string, string>>({});
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadAssistants();
  }, []);

  const loadAssistants = async () => {
    try {
      const res = await listAssistants();
      setAssistants(res.assistants);
      setDomains(res.domains);
      // Pre-select all active assistants
      setSelected(new Set(res.assistants.filter((a) => a.is_active).map((a) => a.id)));
    } catch (err) {
      console.error("Failed to load assistants:", err);
    } finally {
      setLoading(false);
    }
  };

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleDomain = (domain: string) => {
    const domainAssistants = assistants.filter((a) => a.domain === domain);
    const allSelected = domainAssistants.every((a) => selected.has(a.id));
    setSelected((prev) => {
      const next = new Set(prev);
      for (const a of domainAssistants) {
        if (allSelected) next.delete(a.id);
        else next.add(a.id);
      }
      return next;
    });
  };

  const selectPreset = (preset: string) => {
    if (preset === "all") {
      setSelected(new Set(assistants.map((a) => a.id)));
    } else if (preset === "essential") {
      setSelected(
        new Set(
          assistants
            .filter((a) =>
              ["code-review", "security", "api-design", "database", "product-discovery", "jtbd-requirements"].includes(a.id)
            )
            .map((a) => a.id)
        )
      );
    } else if (preset === "discovery") {
      setSelected(
        new Set(
          assistants
            .filter((a) => a.domain === "project" || a.domain === "ba")
            .map((a) => a.id)
        )
      );
    } else if (preset === "security") {
      setSelected(
        new Set(
          assistants
            .filter((a) => a.domain === "compliance")
            .map((a) => a.id)
        )
      );
    }
  };

  // Group by domain
  const grouped: Record<string, AssistantSummary[]> = {};
  for (const a of assistants) {
    if (!grouped[a.domain]) grouped[a.domain] = [];
    grouped[a.domain].push(a);
  }

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div className="bg-white rounded-2xl p-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-genesis-600 mx-auto" />
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b">
          <h2 className="text-xl font-semibold text-gray-900">
            Choose Your Team
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            Select the AI assistants that will guide discovery and review code
            {initialIdea.length > 80 ? (
              <span className="font-medium text-gray-700 block mt-1 truncate max-w-xl" title={initialIdea}>
                {initialIdea.slice(0, 80)}...
              </span>
            ) : (
              <span className="font-medium text-gray-700"> for: {initialIdea}</span>
            )}
          </p>
        </div>

        {/* Presets */}
        <div className="px-6 py-3 border-b bg-gray-50 flex items-center gap-2 flex-wrap">
          <span className="text-xs font-medium text-gray-500">Presets:</span>
          {[
            { id: "all", label: "All Assistants", count: assistants.length },
            { id: "essential", label: "Essential", count: 6 },
            { id: "discovery", label: "Discovery Only", count: assistants.filter((a) => ["project", "ba"].includes(a.domain)).length },
            { id: "security", label: "Security Focus", count: assistants.filter((a) => a.domain === "compliance").length },
          ].map((preset) => (
            <button
              key={preset.id}
              onClick={() => selectPreset(preset.id)}
              className="px-3 py-1 rounded-full text-xs font-medium border hover:bg-white transition bg-white text-gray-700 border-gray-300"
            >
              {preset.label} ({preset.count})
            </button>
          ))}
          <div className="ml-auto text-xs text-gray-500">
            {selected.size} of {assistants.length} selected
          </div>
        </div>

        {/* Assistant grid */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          <div className="space-y-6">
            {Object.entries(grouped).map(([domain, domainAssistants]) => {
              const allSelected = domainAssistants.every((a) =>
                selected.has(a.id)
              );
              const someSelected = domainAssistants.some((a) =>
                selected.has(a.id)
              );

              return (
                <div key={domain}>
                  <div className="flex items-center gap-2 mb-2">
                    <span>{DOMAIN_ICONS[domain] || "📦"}</span>
                    <h3 className="text-sm font-semibold text-gray-700">
                      {domains[domain] || domain}
                    </h3>
                    <button
                      onClick={() => toggleDomain(domain)}
                      className="text-xs text-genesis-600 hover:text-genesis-700"
                    >
                      {allSelected ? "deselect all" : "select all"}
                    </button>
                    <span className="text-xs text-gray-400">
                      {domainAssistants.filter((a) => selected.has(a.id)).length}/
                      {domainAssistants.length}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 lg:grid-cols-3 gap-2">
                    {domainAssistants.map((a) => (
                      <button
                        key={a.id}
                        onClick={() => toggle(a.id)}
                        className={`p-3 rounded-lg border text-left transition ${
                          selected.has(a.id)
                            ? `${DOMAIN_COLORS[domain] || "bg-blue-50 border-blue-200"} ring-2 ring-genesis-400`
                            : "bg-white border-gray-200 opacity-60 hover:opacity-100"
                        }`}
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex-1 min-w-0">
                            <div className="text-sm font-medium text-gray-800 truncate">
                              {a.name}
                            </div>
                            <div className="text-xs text-gray-500 mt-0.5 line-clamp-2">
                              {a.description}
                            </div>
                          </div>
                          <div
                            className={`w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0 ml-2 ${
                              selected.has(a.id)
                                ? "bg-genesis-600 border-genesis-600"
                                : "border-gray-300"
                            }`}
                          >
                            {selected.has(a.id) && (
                              <svg
                                className="w-3 h-3 text-white"
                                fill="none"
                                stroke="currentColor"
                                viewBox="0 0 24 24"
                              >
                                <path
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                  strokeWidth={3}
                                  d="M5 13l4 4L19 7"
                                />
                              </svg>
                            )}
                          </div>
                        </div>
                        {a.weight > 1.5 && (
                          <div className="mt-1">
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-700">
                              weight: {a.weight}x
                            </span>
                          </div>
                        )}
                      </button>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t bg-gray-50 flex items-center justify-between">
          <div className="text-sm text-gray-500">
            {selected.size} assistants will guide your build
          </div>
          <div className="flex gap-3">
            <button
              onClick={onCancel}
              className="px-4 py-2 border rounded-lg text-gray-600 hover:bg-white transition"
            >
              Cancel
            </button>
            <button
              onClick={() => onStart(Array.from(selected))}
              disabled={selected.size === 0}
              className="px-6 py-2 bg-genesis-600 text-white rounded-lg hover:bg-genesis-700 disabled:opacity-50 transition font-medium"
            >
              Start Discovery →
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
