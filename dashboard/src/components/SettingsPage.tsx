"use client";

import { useEffect, useState } from "react";
import { getToken } from "@/lib/api";

interface Settings {
  tenant_id: string;
  tenant_name: string;
  plan: string;
  credits_used: number;
  credits_limit: number;
  max_concurrent_builds: number;
  has_api_key: boolean;
  api_key_preview: string;
  auth_method: string;
}

const API_BASE =
  typeof window !== "undefined" && window.location.hostname !== "localhost"
    ? ""
    : "http://localhost:8000";

export function SettingsPage({ onBack }: { onBack: () => void }) {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<any>(null);
  const [message, setMessage] = useState("");

  const headers = () => ({
    Authorization: `Bearer ${getToken()}`,
    "Content-Type": "application/json",
  });

  const loadSettings = async () => {
    const res = await fetch(`${API_BASE}/api/v1/settings`, { headers: headers() });
    if (res.ok) setSettings(await res.json());
  };

  useEffect(() => {
    loadSettings();
  }, []);

  const handleSaveKey = async () => {
    if (!apiKey.trim()) return;
    setSaving(true);
    setMessage("");
    try {
      const res = await fetch(`${API_BASE}/api/v1/settings/api-key`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({ api_key: apiKey }),
      });
      if (res.ok) {
        setMessage("API key saved!");
        setApiKey("");
        loadSettings();
      } else {
        const err = await res.json();
        setMessage(`Error: ${err.detail}`);
      }
    } catch (e: any) {
      setMessage(`Error: ${e.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleTestConnection = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/settings/test-connection`, {
        method: "POST",
        headers: headers(),
      });
      const data = await res.json();
      setTestResult(data);
    } catch (e: any) {
      setTestResult({ status: "error", error: e.message });
    } finally {
      setTesting(false);
    }
  };

  const handleRemoveKey = async () => {
    if (!confirm("Remove API key? Claude will stop working for all builds.")) return;
    await fetch(`${API_BASE}/api/v1/settings/api-key`, {
      method: "DELETE",
      headers: headers(),
    });
    loadSettings();
    setMessage("API key removed");
  };

  if (!settings) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-genesis-600" />
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center gap-3 mb-8">
        <button onClick={onBack} className="text-gray-400 hover:text-gray-600 text-sm">
          ← Back
        </button>
        <h2 className="text-2xl font-semibold text-gray-900">Settings</h2>
      </div>

      <div className="max-w-2xl space-y-8">
        {/* Claude Connection */}
        <div className="bg-white border rounded-xl p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-1">Claude Connection</h3>
          <p className="text-sm text-gray-500 mb-4">
            Connect your Anthropic API key to power AI discovery, code generation, and code review.
          </p>

          {/* Current status */}
          <div className={`flex items-center gap-3 p-4 rounded-lg mb-4 ${
            settings.has_api_key ? "bg-green-50 border border-green-200" : "bg-amber-50 border border-amber-200"
          }`}>
            <span className={`w-3 h-3 rounded-full ${settings.has_api_key ? "bg-green-500" : "bg-amber-500"}`} />
            <div>
              <div className={`text-sm font-medium ${settings.has_api_key ? "text-green-800" : "text-amber-800"}`}>
                {settings.has_api_key ? "Connected" : "Not Connected"}
              </div>
              {settings.has_api_key && (
                <div className="text-xs text-green-600 font-mono mt-0.5">
                  {settings.api_key_preview}
                </div>
              )}
              {!settings.has_api_key && (
                <div className="text-xs text-amber-600 mt-0.5">
                  Add your API key to enable Claude-powered builds
                </div>
              )}
            </div>
          </div>

          {/* API Key input */}
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Anthropic API Key
              </label>
              <div className="flex gap-2">
                <input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="sk-ant-api03-..."
                  className="flex-1 px-3 py-2 border rounded-lg text-sm font-mono focus:ring-2 focus:ring-genesis-500 focus:outline-none"
                />
                <button
                  onClick={handleSaveKey}
                  disabled={saving || !apiKey.trim()}
                  className="px-4 py-2 bg-genesis-600 text-white rounded-lg text-sm hover:bg-genesis-700 disabled:opacity-50 transition"
                >
                  {saving ? "Saving..." : "Save Key"}
                </button>
              </div>
              <p className="text-xs text-gray-400 mt-1">
                Get your key from{" "}
                <a
                  href="https://console.anthropic.com/settings/keys"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-genesis-600 hover:underline"
                >
                  console.anthropic.com
                </a>
              </p>
            </div>

            {message && (
              <p className={`text-sm ${message.startsWith("Error") ? "text-red-500" : "text-green-600"}`}>
                {message}
              </p>
            )}

            {/* Test + Remove */}
            {settings.has_api_key && (
              <div className="flex gap-2 pt-2">
                <button
                  onClick={handleTestConnection}
                  disabled={testing}
                  className="px-4 py-2 border rounded-lg text-sm text-genesis-600 hover:bg-genesis-50 transition"
                >
                  {testing ? "Testing..." : "Test Connection"}
                </button>
                <button
                  onClick={handleRemoveKey}
                  className="px-4 py-2 border border-red-200 rounded-lg text-sm text-red-600 hover:bg-red-50 transition"
                >
                  Remove Key
                </button>
              </div>
            )}

            {/* Test result */}
            {testResult && (
              <div className={`p-3 rounded-lg text-sm ${
                testResult.status === "connected"
                  ? "bg-green-50 text-green-800 border border-green-200"
                  : "bg-red-50 text-red-800 border border-red-200"
              }`}>
                {testResult.status === "connected" ? (
                  <>
                    <div className="font-medium">Claude responded!</div>
                    <div className="text-xs mt-1 font-mono">{testResult.response}</div>
                    {testResult.cost_usd && (
                      <div className="text-xs mt-1">Cost: ${testResult.cost_usd.toFixed(4)}</div>
                    )}
                  </>
                ) : (
                  <>
                    <div className="font-medium">Connection failed</div>
                    <div className="text-xs mt-1">{testResult.error}</div>
                  </>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Account Info */}
        <div className="bg-white border rounded-xl p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Account</h3>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-gray-500">Organization</span>
              <div className="font-medium text-gray-900">{settings.tenant_name}</div>
            </div>
            <div>
              <span className="text-gray-500">Plan</span>
              <div className="font-medium text-gray-900 capitalize">{settings.plan}</div>
            </div>
            <div>
              <span className="text-gray-500">Credits Used</span>
              <div className="font-medium text-gray-900">
                ${settings.credits_used.toFixed(2)} / ${settings.credits_limit.toFixed(2)}
              </div>
            </div>
            <div>
              <span className="text-gray-500">Max Concurrent Builds</span>
              <div className="font-medium text-gray-900">{settings.max_concurrent_builds}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
