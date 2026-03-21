"use client";

import { type ConversationState } from "@/lib/api";

/**
 * Discovery Board — shows the evolving understanding of the project.
 *
 * As the user converses with Claude, this sidebar updates to show:
 * - Scanned websites and what was learned
 * - Uploaded documents
 * - Emerging user personas
 * - Key problems identified
 * - Feature ideas and scope
 * - Discovery progress indicator
 */

function ProgressRing({
  progress,
  label,
}: {
  progress: number;
  label: string;
}) {
  const radius = 30;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (progress / 100) * circumference;

  return (
    <div className="flex flex-col items-center">
      <svg className="w-16 h-16 -rotate-90">
        <circle
          cx="32"
          cy="32"
          r={radius}
          stroke="#e5e7eb"
          strokeWidth="4"
          fill="none"
        />
        <circle
          cx="32"
          cy="32"
          r={radius}
          stroke="#4f6ef7"
          strokeWidth="4"
          fill="none"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className="transition-all duration-500"
        />
      </svg>
      <span className="text-xs text-gray-500 mt-1">{label}</span>
      <span className="text-lg font-bold text-genesis-700">{progress}%</span>
    </div>
  );
}

function SectionCard({
  title,
  icon,
  items,
  emptyText,
  color = "blue",
}: {
  title: string;
  icon: string;
  items: string[];
  emptyText: string;
  color?: string;
}) {
  const bgColor = {
    blue: "bg-blue-50 border-blue-200",
    purple: "bg-purple-50 border-purple-200",
    green: "bg-green-50 border-green-200",
    amber: "bg-amber-50 border-amber-200",
    red: "bg-red-50 border-red-200",
  }[color] || "bg-gray-50 border-gray-200";

  const textColor = {
    blue: "text-blue-700",
    purple: "text-purple-700",
    green: "text-green-700",
    amber: "text-amber-700",
    red: "text-red-700",
  }[color] || "text-gray-700";

  return (
    <div className={`rounded-lg border p-3 ${bgColor}`}>
      <div className={`text-xs font-semibold ${textColor} mb-2`}>
        {icon} {title}
      </div>
      {items.length > 0 ? (
        <ul className="space-y-1">
          {items.map((item, i) => (
            <li key={i} className="text-xs text-gray-700 flex items-start gap-1">
              <span className="text-gray-400 mt-0.5">•</span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-gray-400 italic">{emptyText}</p>
      )}
    </div>
  );
}

export function DiscoveryBoard({ state }: { state: ConversationState }) {
  const ctx = state.context || {};
  const uploads = ctx.uploads || [];
  const scans = ctx.scans || [];
  const messages = state.messages || [];

  // Extract insights from the conversation
  const assistantMessages = messages
    .filter((m) => m.role === "assistant")
    .map((m) => m.content);
  const userMessages = messages
    .filter((m) => m.role === "user")
    .map((m) => m.content);

  // Analyze conversation coverage
  const allText = [...assistantMessages, ...userMessages].join(" ").toLowerCase();
  const hasPersona = /who|user|customer|patient|doctor|role|persona/.test(allText);
  const hasProblem = /problem|pain|frustrat|struggle|challeng|issue/.test(allText);
  const hasFeatures = /feature|function|capabil|need|want|should/.test(allText);
  const hasScope = /scope|mvp|first version|priority|must.?have/.test(allText);
  const hasConstraints = /compliance|integrat|budget|timeline|constraint/.test(allText);

  // Calculate discovery progress
  const checks = [
    messages.length >= 2,  // Started conversation
    hasPersona,            // Discussed who
    hasProblem,           // Discussed why
    hasFeatures,          // Discussed what
    uploads.length > 0 || scans.length > 0,  // Shared reference material
    hasScope,             // Discussed scope
    hasConstraints,       // Discussed constraints
    messages.length >= 8,  // Deep enough conversation
  ];
  const progress = Math.round((checks.filter(Boolean).length / checks.length) * 100);

  // Extract key topics from assistant messages
  const extractTopics = (keyword: string): string[] => {
    const topics: string[] = [];
    for (const msg of assistantMessages) {
      const sentences = msg.split(/[.!?]\s/);
      for (const s of sentences) {
        if (s.toLowerCase().includes(keyword) && s.length > 20 && s.length < 200) {
          topics.push(s.trim());
        }
      }
    }
    return topics.slice(0, 3);
  };

  const personaHints = extractTopics("user");
  const problemHints = extractTopics("problem");
  const featureHints = extractTopics("feature");

  return (
    <div className="w-80 border-l bg-white overflow-y-auto p-4 space-y-4">
      {/* Header */}
      <div className="text-center pb-3 border-b">
        <h3 className="font-semibold text-gray-900">Discovery Board</h3>
        <p className="text-xs text-gray-500 mt-1">
          Building understanding of your project
        </p>
      </div>

      {/* Progress */}
      <div className="flex justify-center">
        <ProgressRing progress={progress} label="Discovery" />
      </div>

      {/* Checklist */}
      <div className="rounded-lg border bg-gray-50 p-3">
        <div className="text-xs font-semibold text-gray-600 mb-2">
          Discovery Checklist
        </div>
        <div className="space-y-1.5">
          {[
            { label: "Started conversation", done: messages.length >= 2 },
            { label: "Identified target users", done: hasPersona },
            { label: "Defined the problem", done: hasProblem },
            { label: "Explored features", done: hasFeatures },
            { label: "Shared references", done: uploads.length > 0 || scans.length > 0 },
            { label: "Scoped first version", done: hasScope },
            { label: "Discussed constraints", done: hasConstraints },
            { label: "Deep enough to proceed", done: messages.length >= 8 },
          ].map((item, i) => (
            <div key={i} className="flex items-center gap-2 text-xs">
              <span className={item.done ? "text-green-500" : "text-gray-300"}>
                {item.done ? "✓" : "○"}
              </span>
              <span className={item.done ? "text-gray-700" : "text-gray-400"}>
                {item.label}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Scanned Websites */}
      <SectionCard
        title="Reference Sites"
        icon="🌐"
        color="purple"
        items={scans.map((s: any) => {
          try {
            return `${new URL(s.url).hostname}${s.summary ? ` — ${s.summary.slice(0, 80)}...` : ""}`;
          } catch {
            return s.url;
          }
        })}
        emptyText="Scan a website for reference"
      />

      {/* Uploaded Files */}
      <SectionCard
        title="Uploaded Materials"
        icon="📎"
        color="blue"
        items={uploads.map((u: any) => `${u.name} (${u.type?.split("/")[1] || "file"})`)}
        emptyText="Upload docs, mockups, or images"
      />

      {/* Emerging Insights */}
      <SectionCard
        title="Users & Personas"
        icon="👤"
        color="green"
        items={personaHints}
        emptyText="Tell Claude about your target users"
      />

      <SectionCard
        title="Problems to Solve"
        icon="🎯"
        color="red"
        items={problemHints}
        emptyText="Describe the problems you're solving"
      />

      <SectionCard
        title="Feature Ideas"
        icon="💡"
        color="amber"
        items={featureHints}
        emptyText="Discuss what you want to build"
      />

      {/* Conversation Stats */}
      <div className="rounded-lg border bg-gray-50 p-3">
        <div className="text-xs font-semibold text-gray-600 mb-2">
          Session Stats
        </div>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div>
            <span className="text-gray-400">Messages</span>
            <div className="font-semibold text-gray-700">{messages.length}</div>
          </div>
          <div>
            <span className="text-gray-400">Your inputs</span>
            <div className="font-semibold text-gray-700">{userMessages.length}</div>
          </div>
          <div>
            <span className="text-gray-400">Files</span>
            <div className="font-semibold text-gray-700">{uploads.length}</div>
          </div>
          <div>
            <span className="text-gray-400">Sites scanned</span>
            <div className="font-semibold text-gray-700">{scans.length}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
