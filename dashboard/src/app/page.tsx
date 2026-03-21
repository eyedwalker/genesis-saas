"use client";

import { useEffect, useState } from "react";
import { getToken } from "@/lib/api";
import { LoginForm } from "@/components/LoginForm";
import { Dashboard } from "@/components/Dashboard";

export default function Home() {
  const [isAuthed, setIsAuthed] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getToken();
    setIsAuthed(!!token);
    setLoading(false);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-genesis-600" />
      </div>
    );
  }

  if (!isAuthed) {
    return <LoginForm onSuccess={() => setIsAuthed(true)} />;
  }

  return <Dashboard />;
}
