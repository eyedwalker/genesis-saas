"use client";

import { useState } from "react";
import {
  type Factory,
  type Build,
  listBuilds,
  createBuild,
} from "@/lib/api";

const STAGE_COLORS: Record<string, string> = {
  requirements: "bg-blue-100 text-blue-800",
  requirements_review: "bg-yellow-100 text-yellow-800",
  design: "bg-purple-100 text-purple-800",
  design_review: "bg-yellow-100 text-yellow-800",
  planning: "bg-indigo-100 text-indigo-800",
  plan_review: "bg-yellow-100 text-yellow-800",
  building: "bg-orange-100 text-orange-800",
  reviewing: "bg-pink-100 text-pink-800",
  code_review: "bg-yellow-100 text-yellow-800",
  qa_review: "bg-yellow-100 text-yellow-800",
  deliverable_review: "bg-yellow-100 text-yellow-800",
  approved: "bg-green-100 text-green-800",
  exported: "bg-emerald-100 text-emerald-800",
  failed: "bg-red-100 text-red-800",
};

function VibeScore({ score, grade }: { score: number | null; grade: string | null }) {
  if (score === null) return null;
  const color =
    score >= 90
      ? "text-green-600"
      : score >= 70
      ? "text-yellow-600"
      : "text-red-600";
  return (
    <span className={`font-mono font-bold ${color}`}>
      {score} ({grade})
    </span>
  );
}

function FactoryCard({
  factory,
  onSelectBuild,
  onRefresh,
}: {
  factory: Factory;
  onSelectBuild: (id: string) => void;
  onRefresh: () => void;
}) {
  const [builds, setBuilds] = useState<Build[]>([]);
  const [expanded, setExpanded] = useState(false);
  const [newFeature, setNewFeature] = useState("");
  const [loading, setLoading] = useState(false);

  const loadBuilds = async () => {
    const res = await listBuilds(factory.id);
    setBuilds(res.builds);
  };

  const toggleExpand = async () => {
    if (!expanded) await loadBuilds();
    setExpanded(!expanded);
  };

  const handleNewBuild = async () => {
    if (!newFeature.trim()) return;
    setLoading(true);
    try {
      const build = await createBuild({
        factory_id: factory.id,
        feature_request: newFeature,
      });
      setNewFeature("");
      onSelectBuild(build.id);
    } catch (err: any) {
      alert(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
      <div
        className="p-5 cursor-pointer hover:bg-gray-50 transition"
        onClick={toggleExpand}
      >
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-lg text-gray-900">
              {factory.name}
            </h3>
            <p className="text-sm text-gray-500 mt-1">
              {factory.domain} · {factory.tech_stack || "No stack"}
            </p>
          </div>
          <div className="flex items-center gap-4 text-sm">
            <span className="text-gray-500">{factory.build_count} builds</span>
            {factory.avg_vibe_score !== null && (
              <span className="font-mono text-gray-600">
                Avg: {factory.avg_vibe_score}
              </span>
            )}
            <span
              className={`px-2 py-1 rounded text-xs font-medium ${
                factory.status === "active"
                  ? "bg-green-100 text-green-700"
                  : "bg-gray-100 text-gray-600"
              }`}
            >
              {factory.status}
            </span>
            <span className="text-gray-300">
              {expanded ? "▲" : "▼"}
            </span>
          </div>
        </div>
        {factory.description && (
          <p className="text-sm text-gray-600 mt-2">{factory.description}</p>
        )}
      </div>

      {expanded && (
        <div className="border-t px-5 py-4 bg-gray-50">
          {/* New build input */}
          <div className="flex gap-2 mb-4">
            <input
              type="text"
              value={newFeature}
              onChange={(e) => setNewFeature(e.target.value)}
              placeholder="Describe a feature to build..."
              className="flex-1 px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-genesis-500 focus:outline-none"
              onKeyDown={(e) => e.key === "Enter" && handleNewBuild()}
            />
            <button
              onClick={handleNewBuild}
              disabled={loading || !newFeature.trim()}
              className="px-4 py-2 bg-genesis-600 text-white rounded-lg text-sm hover:bg-genesis-700 disabled:opacity-50 transition"
            >
              {loading ? "..." : "Build"}
            </button>
          </div>

          {/* Builds list */}
          {builds.length === 0 ? (
            <p className="text-sm text-gray-400">No builds yet</p>
          ) : (
            <div className="space-y-2">
              {builds.map((build) => (
                <div
                  key={build.id}
                  className="flex items-center justify-between p-3 bg-white rounded-lg border cursor-pointer hover:border-genesis-300 transition"
                  onClick={() => onSelectBuild(build.id)}
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-800 truncate">
                      {build.feature_request}
                    </p>
                    <p className="text-xs text-gray-400 mt-1">
                      {new Date(build.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <div className="flex items-center gap-3 ml-4">
                    <VibeScore
                      score={build.vibe_score}
                      grade={build.vibe_grade}
                    />
                    <span
                      className={`px-2 py-1 rounded text-xs font-medium ${
                        STAGE_COLORS[build.status] || "bg-gray-100 text-gray-600"
                      }`}
                    >
                      {build.status.replace(/_/g, " ")}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function FactoryList({
  factories,
  onSelectBuild,
  onRefresh,
}: {
  factories: Factory[];
  onSelectBuild: (id: string) => void;
  onRefresh: () => void;
}) {
  if (factories.length === 0) {
    return (
      <div className="text-center py-16 text-gray-400">
        <p className="text-lg">No factories yet</p>
        <p className="text-sm mt-1">
          Create your first factory to start building
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {factories.map((f) => (
        <FactoryCard
          key={f.id}
          factory={f}
          onSelectBuild={onSelectBuild}
          onRefresh={onRefresh}
        />
      ))}
    </div>
  );
}
