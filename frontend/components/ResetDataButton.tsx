"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { API_BASE_URL } from "@/lib/api";

export default function ResetDataButton() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleClick = async () => {
    const confirmed = window.confirm(
      "This deletes every session and your entire learner profile — there's no undo. Continue?"
    );
    if (!confirmed) return;

    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/data`, { method: "DELETE" });
      if (!res.ok) throw new Error(`Request failed: ${res.status}`);
      router.refresh();
    } catch {
      setError("Couldn't clear data — is the backend reachable?");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        onClick={handleClick}
        disabled={busy}
        className="rounded-md border border-red-500/30 px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-500/10 disabled:opacity-50 dark:text-red-400"
      >
        {busy ? "Clearing…" : "Clear all data"}
      </button>
      {error && <span className="text-xs text-red-600 dark:text-red-400">{error}</span>}
    </div>
  );
}
