"use client";

import { type ConversationState } from "@/lib/api";

/**
 * Discovery Board — living document showing what's being built.
 *
 * Shows real artifacts extracted from the conversation:
 * - Personas identified from user descriptions
 * - Features requested and discussed
 * - Problems being solved
 * - Constraints and compliance needs
 * - Website scan results with real data
 * - File analysis with extracted structure
 * - Discovery progress as a percentage
 */

function ProgressBar({ percent, label }: { percent: number; label: string }) {
  return (
    <div className="mb-4">
      <div className="flex justify-between text-xs mb-1">
        <span className="font-medium text-gray-700">{label}</span>
        <span className="text-genesis-600 font-bold">{percent}%</span>
      </div>
      <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-genesis-500 to-genesis-600 rounded-full transition-all duration-500"
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}

function ArtifactSection({
  title,
  icon,
  children,
  count,
  color = "gray",
}: {
  title: string;
  icon: string;
  children: React.ReactNode;
  count?: number;
  color?: string;
}) {
  const borderColor = {
    blue: "border-l-blue-500",
    green: "border-l-green-500",
    red: "border-l-red-500",
    amber: "border-l-amber-500",
    purple: "border-l-purple-500",
    pink: "border-l-pink-500",
    gray: "border-l-gray-400",
  }[color] || "border-l-gray-400";

  return (
    <div className={`border-l-4 ${borderColor} bg-white rounded-r-lg p-3 shadow-sm`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold text-gray-700">
          {icon} {title}
        </span>
        {count !== undefined && (
          <span className="text-[10px] bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded-full">
            {count}
          </span>
        )}
      </div>
      {children}
    </div>
  );
}

function PersonaCard({ persona }: { persona: { role: string; context: string } }) {
  return (
    <div className="flex items-start gap-2 py-1.5">
      <span className="w-6 h-6 rounded-full bg-green-100 text-green-700 flex items-center justify-center text-[10px] font-bold flex-shrink-0">
        {persona.role[0]}
      </span>
      <div>
        <div className="text-xs font-medium text-gray-800">{persona.role}</div>
        {persona.context && (
          <div className="text-[11px] text-gray-500 mt-0.5 line-clamp-2">
            {persona.context}
          </div>
        )}
      </div>
    </div>
  );
}

function ScanCard({ scan }: { scan: any }) {
  return (
    <div className="py-2 border-b last:border-0">
      <div className="flex items-start gap-2">
        <span className="text-purple-500 mt-0.5">🌐</span>
        <div className="flex-1 min-w-0">
          <div className="text-xs font-medium text-gray-800 truncate">
            {scan.title || scan.hostname || scan.url}
          </div>
          {scan.description && (
            <div className="text-[11px] text-gray-500 mt-0.5 line-clamp-2">
              {scan.description}
            </div>
          )}
          {scan.tech_stack && scan.tech_stack.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-1">
              {scan.tech_stack.map((t: string) => (
                <span
                  key={t}
                  className="text-[9px] px-1.5 py-0.5 rounded bg-purple-50 text-purple-700"
                >
                  {t}
                </span>
              ))}
            </div>
          )}
          {scan.navigation && scan.navigation.length > 0 && (
            <div className="text-[10px] text-gray-400 mt-1">
              Pages: {scan.navigation.slice(0, 5).map((n: any) => n.label).join(", ")}
            </div>
          )}
          <div className="flex gap-2 mt-1">
            {scan.has_login && (
              <span className="text-[9px] px-1 py-0.5 rounded bg-blue-50 text-blue-600">Auth</span>
            )}
            {scan.has_pricing && (
              <span className="text-[9px] px-1 py-0.5 rounded bg-green-50 text-green-600">Pricing</span>
            )}
            {scan.has_forms && (
              <span className="text-[9px] px-1 py-0.5 rounded bg-amber-50 text-amber-600">Forms</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function UploadCard({ upload }: { upload: any }) {
  return (
    <div className="py-2 border-b last:border-0">
      <div className="flex items-start gap-2">
        <span className="text-blue-500 mt-0.5">📎</span>
        <div className="flex-1 min-w-0">
          <div className="text-xs font-medium text-gray-800">{upload.name}</div>
          <div className="text-[11px] text-gray-500 mt-0.5">
            {upload.summary}
          </div>
          {upload.columns && (
            <div className="text-[10px] text-gray-400 mt-1">
              Columns: {upload.columns.slice(0, 6).join(", ")}
              {upload.columns.length > 6 && ` (+${upload.columns.length - 6})`}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function DiscoveryBoard({ state }: { state: ConversationState }) {
  const artifacts = state.artifacts || {};
  const progress = artifacts.progress || {};
  const personas = artifacts.personas || [];
  const features = artifacts.features || [];
  const problems = artifacts.problems || [];
  const constraints = artifacts.constraints || [];
  const scans = artifacts.scans || [];
  const uploads = artifacts.uploads || [];

  const hasContent =
    personas.length > 0 ||
    features.length > 0 ||
    problems.length > 0 ||
    constraints.length > 0 ||
    scans.length > 0 ||
    uploads.length > 0;

  return (
    <div className="w-80 border-l bg-gray-50 overflow-y-auto flex flex-col">
      {/* Header */}
      <div className="px-4 py-3 bg-white border-b sticky top-0 z-10">
        <h3 className="font-semibold text-gray-900 text-sm">Discovery Board</h3>
        <p className="text-[11px] text-gray-500">
          What we know so far
        </p>
      </div>

      {/* Progress */}
      <div className="px-4 pt-4">
        <ProgressBar
          percent={progress.percent || 0}
          label="Discovery Progress"
        />
      </div>

      {/* Checklist */}
      <div className="px-4 pb-3">
        <div className="grid grid-cols-2 gap-x-3 gap-y-1">
          {[
            { label: "Users", done: progress.personas_identified },
            { label: "Problems", done: progress.problems_defined },
            { label: "Features", done: progress.features_explored },
            { label: "Constraints", done: progress.constraints_identified },
            { label: "References", done: progress.references_shared },
            { label: "Scope", done: progress.scope_discussed },
          ].map((item) => (
            <div key={item.label} className="flex items-center gap-1.5 text-[11px]">
              <span className={item.done ? "text-green-500" : "text-gray-300"}>
                {item.done ? "●" : "○"}
              </span>
              <span className={item.done ? "text-gray-700" : "text-gray-400"}>
                {item.label}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Artifacts */}
      <div className="flex-1 px-3 pb-4 space-y-3">
        {/* Scanned Websites */}
        {scans.length > 0 && (
          <ArtifactSection title="Reference Sites" icon="🌐" count={scans.length} color="purple">
            {scans.map((s: any, i: number) => (
              <ScanCard key={i} scan={s} />
            ))}
          </ArtifactSection>
        )}

        {/* Uploaded Files */}
        {uploads.length > 0 && (
          <ArtifactSection title="Uploaded Materials" icon="📎" count={uploads.length} color="blue">
            {uploads.map((u: any, i: number) => (
              <UploadCard key={i} upload={u} />
            ))}
          </ArtifactSection>
        )}

        {/* Personas */}
        {personas.length > 0 && (
          <ArtifactSection title="Users & Personas" icon="👤" count={personas.length} color="green">
            {personas.map((p: any, i: number) => (
              <PersonaCard key={i} persona={p} />
            ))}
          </ArtifactSection>
        )}

        {/* Problems */}
        {problems.length > 0 && (
          <ArtifactSection title="Problems to Solve" icon="🎯" count={problems.length} color="red">
            <ul className="space-y-1.5">
              {problems.map((p: string, i: number) => (
                <li key={i} className="text-[11px] text-gray-700 flex items-start gap-1.5">
                  <span className="text-red-400 mt-0.5 flex-shrink-0">•</span>
                  <span>{p}</span>
                </li>
              ))}
            </ul>
          </ArtifactSection>
        )}

        {/* Features */}
        {features.length > 0 && (
          <ArtifactSection title="Features Identified" icon="💡" count={features.length} color="amber">
            <ul className="space-y-1.5">
              {features.map((f: string, i: number) => (
                <li key={i} className="text-[11px] text-gray-700 flex items-start gap-1.5">
                  <span className="text-amber-400 mt-0.5 flex-shrink-0">•</span>
                  <span>{f}</span>
                </li>
              ))}
            </ul>
          </ArtifactSection>
        )}

        {/* Constraints */}
        {constraints.length > 0 && (
          <ArtifactSection title="Constraints & Requirements" icon="🛡️" count={constraints.length} color="pink">
            <div className="flex flex-wrap gap-1">
              {constraints.map((c: string, i: number) => (
                <span
                  key={i}
                  className="text-[10px] px-2 py-1 rounded-full bg-pink-50 text-pink-700 border border-pink-200"
                >
                  {c}
                </span>
              ))}
            </div>
          </ArtifactSection>
        )}

        {/* Empty state */}
        {!hasContent && (
          <div className="text-center py-8 text-gray-400">
            <p className="text-sm">Start talking about your project</p>
            <p className="text-xs mt-1">
              Artifacts will appear here as you describe users, features, and problems
            </p>
          </div>
        )}

        {/* Stats */}
        <div className="bg-white rounded-lg p-3 shadow-sm">
          <div className="grid grid-cols-3 gap-2 text-center">
            <div>
              <div className="text-lg font-bold text-gray-800">{progress.message_count || 0}</div>
              <div className="text-[10px] text-gray-500">Messages</div>
            </div>
            <div>
              <div className="text-lg font-bold text-gray-800">{uploads.length}</div>
              <div className="text-[10px] text-gray-500">Files</div>
            </div>
            <div>
              <div className="text-lg font-bold text-gray-800">{scans.length}</div>
              <div className="text-[10px] text-gray-500">Scans</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
