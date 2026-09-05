import Link from "next/link";

export default function DashboardPage() {
  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="mt-1 text-black/60 dark:text-white/60">
          Practice a real-world scenario, get evaluated, and see what to work on next.
        </p>
      </div>

      <div className="rounded-lg border border-black/10 p-6 dark:border-white/10">
        <h2 className="font-medium">No sessions yet</h2>
        <p className="mt-1 text-sm text-black/60 dark:text-white/60">
          Your grammar, vocabulary, and fluency profile builds up after your first
          scenario. Weaknesses and a recommended next scenario will show up here
          once you have practice history.
        </p>
        <Link
          href="/scenarios"
          className="mt-4 inline-block rounded-md bg-black px-4 py-2 text-sm font-medium text-white hover:bg-black/80 dark:bg-white dark:text-black dark:hover:bg-white/80"
        >
          Start a scenario
        </Link>
      </div>
    </div>
  );
}
