"use client";

import { useState } from "react";
import { createFactory } from "@/lib/api";

export function CreateFactoryModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [domain, setDomain] = useState("");
  const [description, setDescription] = useState("");
  const [techStack, setTechStack] = useState("Python/FastAPI");
  const [fastTrack, setFastTrack] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await createFactory({
        name,
        domain,
        description: description || undefined,
        tech_stack: techStack || undefined,
        fast_track: fastTrack,
      });
      onCreated();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-2xl shadow-2xl p-6 w-full max-w-lg">
        <h2 className="text-xl font-semibold mb-4">Create Factory</h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Factory Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Healthcare Factory"
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-genesis-500 focus:outline-none"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Domain
            </label>
            <input
              type="text"
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              placeholder="e.g. healthcare, ecommerce, fintech"
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-genesis-500 focus:outline-none"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Description
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What does this factory build?"
              rows={3}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-genesis-500 focus:outline-none resize-none"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Tech Stack
            </label>
            <select
              value={techStack}
              onChange={(e) => setTechStack(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-genesis-500 focus:outline-none"
            >
              <option>Python/FastAPI</option>
              <option>TypeScript/Next.js</option>
              <option>TypeScript/Express</option>
              <option>Go/Gin</option>
              <option>Java/Spring Boot</option>
            </select>
          </div>

          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={fastTrack}
              onChange={(e) => setFastTrack(e.target.checked)}
              className="rounded"
            />
            <span className="text-sm text-gray-700">
              Fast Track (auto-approve all gates)
            </span>
          </label>

          {error && <p className="text-red-500 text-sm">{error}</p>}

          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2 border rounded-lg text-gray-600 hover:bg-gray-50 transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 py-2 bg-genesis-600 text-white rounded-lg hover:bg-genesis-700 disabled:opacity-50 transition"
            >
              {loading ? "Creating..." : "Create Factory"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
