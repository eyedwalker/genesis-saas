"use client";

import { useEffect, useState } from "react";
import { getBuild, advanceBuild, approveBuild, type Build } from "@/lib/api";

const PIPELINE_STAGES = [
  "requirements",
  "requirements_review",
  "design",
  "design_review",
  "planning",
  "plan_review",
  "building",
  "reviewing",
  "code_review",
  "qa_review",
  "deliverable_review",
  "approved",
  "exported",
];

const GATE_STAGES = new Set([
  "requirements_review",
  "design_review",
  "plan_review",
  "code_review",
  "qa_review",
  "deliverable_review",
]);

function PipelineProgress({ currentStage }: { currentStage: string }) {
  const currentIndex = PIPELINE_STAGES.indexOf(currentStage);

  return (
    <div className="flex items-center gap-1 overflow-x-auto py-2">
      {PIPELINE_STAGES.map((stage, i) => {
        const isCompleted = i < currentIndex;
        const isCurrent = stage === currentStage;
        const isGate = GATE_STAGES.has(stage);
        const label = stage.replace(/_/g, " ");

        return (
          <div key={stage} className="flex items-center">
            <div
              className={`px-2 py-1 rounded text-xs font-medium whitespace-nowrap ${
                isCurrent
                  ? isGate
                    ? "bg-yellow-200 text-yellow-900 ring-2 ring-yellow-400"
                    : "bg-genesis-100 text-genesis-800 ring-2 ring-genesis-400"
                  : isCompleted
                  ? "bg-green-100 text-green-700"
                  : "bg-gray-100 text-gray-400"
              }`}
            >
              {isGate ? "⏸ " : ""}
              {label}
            </div>
            {i < PIPELINE_STAGES.length - 1 && (
              <div
                className={`w-4 h-0.5 ${
                  isCompleted ? "bg-green-400" : "bg-gray-200"
                }`}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

function FileTree({
  fileMap,
  selected,
  onSelect,
}: {
  fileMap: Record<string, string>;
  selected: string | null;
  onSelect: (path: string) => void;
}) {
  const files = Object.keys(fileMap).sort();
  return (
    <div className="border rounded-lg overflow-hidden">
      <div className="bg-gray-100 px-3 py-2 text-xs font-medium text-gray-600 border-b">
        Files ({files.length})
      </div>
      <div className="max-h-96 overflow-y-auto">
        {files.map((path) => (
          <div
            key={path}
            className={`px-3 py-1.5 text-sm cursor-pointer hover:bg-gray-50 ${
              selected === path ? "bg-genesis-50 text-genesis-700" : "text-gray-700"
            }`}
            onClick={() => onSelect(path)}
          >
            {path}
          </div>
        ))}
      </div>
    </div>
  );
}

export function BuildView({
  buildId,
  onBack,
}: {
  buildId: string;
  onBack: () => void;
}) {
  const [build, setBuild] = useState<Build | null>(null);
  const [loading, setLoading] = useState(true);
  const [advancing, setAdvancing] = useState(false);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [approveComment, setApproveComment] = useState("");

  const refresh = async () => {
    const b = await getBuild(buildId);
    setBuild(b);
    setLoading(false);
  };

  useEffect(() => {
    refresh();
    // Poll for updates every 3s while build is active
    const interval = setInterval(refresh, 3000);
    return () => clearInterval(interval);
  }, [buildId]);

  const handleAdvance = async () => {
    setAdvancing(true);
    try {
      const updated = await advanceBuild(buildId);
      setBuild(updated);
    } catch (err: any) {
      console.error(err.message);
    } finally {
      setAdvancing(false);
    }
  };

  const handleApprove = async (decision: string) => {
    setAdvancing(true);
    const gateType = build?.status.replace("_review", "") || "";
    try {
      const updated = await approveBuild(buildId, {
        type: gateType,
        decision,
        comment: approveComment || undefined,
      });
      setBuild(updated);
      setApproveComment("");
    } catch (err: any) {
      console.error(err.message);
    } finally {
      setAdvancing(false);
    }
  };

  if (loading || !build) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-genesis-600" />
      </div>
    );
  }

  const isAtGate = GATE_STAGES.has(build.status);
  const isTerminal = ["exported", "failed", "approved"].includes(build.status);

  return (
    <div>
      {/* Header */}
      <div className="flex items-center gap-4 mb-6">
        <button
          onClick={onBack}
          className="text-gray-400 hover:text-gray-600 text-sm"
        >
          ← Back
        </button>
        <div className="flex-1">
          <h2 className="text-xl font-semibold text-gray-900">
            {build.feature_request}
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            Build {build.id.slice(0, 8)} · {build.build_mode} ·{" "}
            {build.iterations} iteration{build.iterations !== 1 ? "s" : ""}
          </p>
        </div>
        {build.vibe_score !== null && (
          <div className="text-center">
            <div
              className={`text-3xl font-bold ${
                build.vibe_score >= 90
                  ? "text-green-600"
                  : build.vibe_score >= 70
                  ? "text-yellow-600"
                  : "text-red-600"
              }`}
            >
              {build.vibe_score}
            </div>
            <div className="text-xs text-gray-500">Vibe Score</div>
          </div>
        )}
      </div>

      {/* Pipeline progress */}
      <PipelineProgress currentStage={build.status} />

      {/* Action bar */}
      <div className="flex items-center gap-3 mt-4 mb-6">
        {isAtGate && (
          <>
            <input
              type="text"
              value={approveComment}
              onChange={(e) => setApproveComment(e.target.value)}
              placeholder="Optional comment..."
              className="flex-1 px-3 py-2 border rounded-lg text-sm"
            />
            <button
              onClick={() => handleApprove("approved")}
              disabled={advancing}
              className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm hover:bg-green-700 disabled:opacity-50"
            >
              Approve
            </button>
            <button
              onClick={() => handleApprove("changes_requested")}
              disabled={advancing}
              className="px-4 py-2 bg-yellow-500 text-white rounded-lg text-sm hover:bg-yellow-600 disabled:opacity-50"
            >
              Request Changes
            </button>
            <button
              onClick={() => handleApprove("rejected")}
              disabled={advancing}
              className="px-4 py-2 bg-red-500 text-white rounded-lg text-sm hover:bg-red-600 disabled:opacity-50"
            >
              Reject
            </button>
          </>
        )}
        {!isAtGate && !isTerminal && (
          <button
            onClick={handleAdvance}
            disabled={advancing}
            className="px-4 py-2 bg-genesis-600 text-white rounded-lg text-sm hover:bg-genesis-700 disabled:opacity-50"
          >
            {advancing ? "Running..." : "Advance Pipeline"}
          </button>
        )}
        {build.status === "failed" && (
          <span className="text-red-600 font-medium">Build Failed</span>
        )}
        {build.status === "exported" && (
          <span className="text-green-600 font-medium">Build Exported</span>
        )}
      </div>

      {/* Content panels */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: artifacts */}
        <div className="space-y-4">
          {build.requirements_data && (
            <details className="bg-white border rounded-xl overflow-hidden">
              <summary className="px-4 py-3 cursor-pointer font-medium text-sm hover:bg-gray-50">
                Requirements ({build.requirements_data.stories?.length || 0}{" "}
                stories)
              </summary>
              <div className="px-4 py-3 border-t text-sm">
                <p className="text-gray-600 mb-3">
                  {build.requirements_data.summary}
                </p>
                {build.requirements_data.stories?.map((s: any) => (
                  <div
                    key={s.id}
                    className="p-2 mb-2 bg-gray-50 rounded text-xs"
                  >
                    <span className="font-mono text-genesis-600">{s.id}</span>{" "}
                    {s.title || `${s.persona}, ${s.capability}`}
                    <span className="ml-2 text-gray-400">({s.priority})</span>
                  </div>
                ))}
              </div>
            </details>
          )}

          {build.plan && (
            <details className="bg-white border rounded-xl overflow-hidden">
              <summary className="px-4 py-3 cursor-pointer font-medium text-sm hover:bg-gray-50">
                Plan — {build.plan.featureName} ({build.plan.steps?.length || 0}{" "}
                steps)
              </summary>
              <div className="px-4 py-3 border-t text-sm space-y-2">
                {build.plan.steps?.map((step: any, i: number) => (
                  <div key={i} className="flex gap-2 text-xs">
                    <span className="text-gray-400 font-mono w-6">
                      {i + 1}.
                    </span>
                    <span className="font-mono text-genesis-600">
                      {step.filePath}
                    </span>
                    <span className="text-gray-600">{step.description}</span>
                  </div>
                ))}
              </div>
            </details>
          )}

          {build.findings && (
            <details className="bg-white border rounded-xl overflow-hidden">
              <summary className="px-4 py-3 cursor-pointer font-medium text-sm hover:bg-gray-50">
                Review Findings (
                {build.findings.findings?.length || 0} issues)
              </summary>
              <div className="px-4 py-3 border-t text-sm space-y-2">
                {build.findings.findings?.map((f: any, i: number) => (
                  <div
                    key={i}
                    className={`p-2 rounded text-xs border-l-4 ${
                      f.severity === "critical"
                        ? "border-red-500 bg-red-50"
                        : f.severity === "high"
                        ? "border-orange-500 bg-orange-50"
                        : f.severity === "medium"
                        ? "border-yellow-500 bg-yellow-50"
                        : "border-gray-300 bg-gray-50"
                    }`}
                  >
                    <div className="font-medium">
                      [{f.severity}] {f.title}
                    </div>
                    <div className="text-gray-600 mt-1">{f.description}</div>
                    {f.recommendation && (
                      <div className="text-genesis-700 mt-1">
                        Fix: {f.recommendation}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>

        {/* Right: code viewer */}
        <div>
          {build.file_map && Object.keys(build.file_map).length > 0 ? (
            <div className="space-y-4">
              <FileTree
                fileMap={build.file_map}
                selected={selectedFile}
                onSelect={setSelectedFile}
              />
              {selectedFile && build.file_map[selectedFile] && (
                <div className="bg-gray-900 rounded-xl overflow-hidden">
                  <div className="bg-gray-800 px-4 py-2 text-xs text-gray-400 font-mono">
                    {selectedFile}
                  </div>
                  <pre className="p-4 text-sm text-gray-100 overflow-x-auto max-h-[600px] overflow-y-auto">
                    <code>{build.file_map[selectedFile]}</code>
                  </pre>
                </div>
              )}
            </div>
          ) : (
            <div className="bg-white border rounded-xl p-8 text-center text-gray-400">
              <p>No code generated yet</p>
              <p className="text-sm mt-1">
                Advance the pipeline to generate code
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
