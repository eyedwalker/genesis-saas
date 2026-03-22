"use client";

import { useEffect, useState } from "react";
import {
  getMe,
  listFactories,
  getSupervisorStatus,
  clearToken,
  startConversation,
  getConversation,
  type Factory,
  type SupervisorStatus,
  type ConversationState,
} from "@/lib/api";
import { FactoryList } from "./FactoryList";
import { CreateFactoryModal } from "./CreateFactoryModal";
import { BuildView } from "./BuildView";
import { ConversationView } from "./ConversationView";
import { AssistantPicker } from "./AssistantPicker";
import { AssistantManager } from "./AssistantManager";
import { SettingsPage } from "./SettingsPage";

type View =
  | { type: "factories" }
  | { type: "assistants" }
  | { type: "settings" }
  | { type: "pickAssistants"; factoryId: string; idea: string }
  | { type: "conversation"; buildId: string; state: ConversationState }
  | { type: "build"; buildId: string };

export function Dashboard() {
  const [user, setUser] = useState<any>(null);
  const [factories, setFactories] = useState<Factory[]>([]);
  const [supervisor, setSupervisor] = useState<SupervisorStatus | null>(null);
  const [view, setView] = useState<View>({ type: "factories" });
  const [showCreate, setShowCreate] = useState(false);

  const refresh = async () => {
    try {
      const [me, facs, sup] = await Promise.all([
        getMe(),
        listFactories(),
        getSupervisorStatus(),
      ]);
      setUser(me);
      setFactories(facs.factories);
      setSupervisor(sup);
    } catch {
      clearToken();
      window.location.reload();
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  // Step 1: User types idea → show assistant picker
  const handleStartBuild = (factoryId: string, idea: string) => {
    setView({ type: "pickAssistants", factoryId, idea });
  };

  // Step 2: User picks assistants → start conversation
  const handleAssistantsChosen = async (
    factoryId: string,
    idea: string,
    assistantIds: string[]
  ) => {
    try {
      const state = await startConversation({
        factory_id: factoryId,
        initial_idea: idea,
        assistant_ids: assistantIds,
      });
      setView({ type: "conversation", buildId: state.build_id, state });
    } catch (err: any) {
      console.error(err.message);
    }
  };

  const handleResumeBuild = async (buildId: string) => {
    try {
      const state = await getConversation(buildId);
      if (state.phase === "discovery") {
        setView({ type: "conversation", buildId, state });
      } else {
        setView({ type: "build", buildId });
      }
    } catch {
      setView({ type: "build", buildId });
    }
  };

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="bg-white border-b px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h1
            className="text-xl font-bold text-genesis-900 cursor-pointer"
            onClick={() => {
              setView({ type: "factories" });
              refresh();
            }}
          >
            Genesis
          </h1>
          {supervisor && (
            <div className="flex gap-3 text-sm text-gray-500">
              <span>{supervisor.total_factories} factories</span>
              <span className="text-gray-300">|</span>
              <span>{supervisor.active_builds} active builds</span>
              <span className="text-gray-300">|</span>
              <span>
                ${supervisor.credits_used.toFixed(2)} / $
                {supervisor.credits_limit.toFixed(2)}
              </span>
            </div>
          )}
        </div>
        <div className="flex items-center gap-4">
          <button
            onClick={() => setView({ type: "assistants" })}
            className="text-sm text-gray-500 hover:text-genesis-600 transition"
          >
            Assistants
          </button>
          <button
            onClick={() => setView({ type: "settings" })}
            className="text-sm text-gray-500 hover:text-genesis-600 transition"
          >
            Settings
          </button>
          <span className="text-sm text-gray-600">
            {user?.name} ({user?.tenant_name})
          </span>
          <button
            onClick={() => {
              clearToken();
              window.location.reload();
            }}
            className="text-sm text-gray-400 hover:text-gray-600"
          >
            Sign out
          </button>
        </div>
      </header>

      {/* Main content */}
      <main
        className={
          view.type === "conversation" ? "" : "max-w-7xl mx-auto px-6 py-8"
        }
      >
        {view.type === "factories" && (
          <>
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-semibold text-gray-900">
                Factories
              </h2>
              <button
                onClick={() => setShowCreate(true)}
                className="px-4 py-2 bg-genesis-600 text-white rounded-lg hover:bg-genesis-700 transition text-sm font-medium"
              >
                + New Factory
              </button>
            </div>
            <FactoryList
              factories={factories}
              onStartBuild={handleStartBuild}
              onSelectBuild={handleResumeBuild}
              onRefresh={refresh}
            />
          </>
        )}

        {view.type === "settings" && (
          <SettingsPage
            onBack={() => {
              setView({ type: "factories" });
              refresh();
            }}
          />
        )}

        {view.type === "assistants" && (
          <AssistantManager
            onBack={() => {
              setView({ type: "factories" });
              refresh();
            }}
          />
        )}

        {view.type === "conversation" && (
          <ConversationView
            buildId={view.buildId}
            initialState={view.state}
            onRequirementsGenerated={(buildId) => {
              setView({ type: "build", buildId });
            }}
            onBack={() => {
              setView({ type: "factories" });
              refresh();
            }}
          />
        )}

        {view.type === "build" && (
          <div className="px-6 py-8">
            <BuildView
              buildId={view.buildId}
              onBack={() => {
                setView({ type: "factories" });
                refresh();
              }}
            />
          </div>
        )}
      </main>

      {/* Assistant Picker modal */}
      {view.type === "pickAssistants" && (
        <AssistantPicker
          factoryId={view.factoryId}
          initialIdea={view.idea}
          onStart={(assistantIds) =>
            handleAssistantsChosen(view.factoryId, view.idea, assistantIds)
          }
          onCancel={() => setView({ type: "factories" })}
        />
      )}

      {showCreate && (
        <CreateFactoryModal
          onClose={() => setShowCreate(false)}
          onCreated={() => {
            setShowCreate(false);
            refresh();
          }}
        />
      )}
    </div>
  );
}
