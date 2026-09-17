import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex flex-col gap-3">
      <h2 className="text-lg font-semibold">Page not found.</h2>
      <p className="text-sm text-black/60 dark:text-white/60">
        That page doesn&apos;t exist.
      </p>
      <Link href="/" className="text-sm underline">
        Back to Dashboard
      </Link>
    </div>
  );
}
