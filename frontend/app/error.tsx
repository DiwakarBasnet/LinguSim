"use client";

import { useEffect } from "react";
import Link from "next/link";

export default function Error({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex flex-col gap-3">
      <h2 className="text-lg font-semibold">Something went wrong.</h2>
      <p className="text-sm text-black/60 dark:text-white/60">
        Check that the backend is running and reachable, then try again.
      </p>
      <div className="flex gap-3">
        <button
          onClick={() => retry()}
          className="rounded-md bg-black px-4 py-2 text-sm font-medium text-white hover:bg-black/80 dark:bg-white dark:text-black dark:hover:bg-white/80"
        >
          Try again
        </button>
        <Link
          href="/"
          className="rounded-md border border-black/10 px-4 py-2 text-sm dark:border-white/10"
        >
          Back to Dashboard
        </Link>
      </div>
    </div>
  );
}
