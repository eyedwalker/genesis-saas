"use client";

import { useEffect, useState } from "react";
import {
  getMe,
  listFactories,
  getSupervisorStatus,
  clearToken,
  type Factory,
  type SupervisorStatus,
} from "@/lib/api";
import { FactoryList } from "./FactoryList";
import { CreateFactoryModal } from "./CreateFactoryModal";
import { BuildView } from "./BuildView";

type View = { type: "factories" } | { type: "build"; buildId: string };

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

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="bg-white border-b px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h1
            className="text-xl font-bold text-genesis-900 cursor-pointer"
            onClick={() => setView({ type: "factories" })}
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
      <main className="max-w-7xl mx-auto px-6 py-8">
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
              onSelectBuild={(buildId) =>
                setView({ type: "build", buildId })
              }
              onRefresh={refresh}
            />
          </>
        )}

        {view.type === "build" && (
          <BuildView
            buildId={view.buildId}
            onBack={() => {
              setView({ type: "factories" });
              refresh();
            }}
          />
        )}
      </main>

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
