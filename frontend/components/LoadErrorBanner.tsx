export default function LoadErrorBanner({ message }: { message: string }) {
  return (
    <p className="rounded-md border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-600 dark:text-red-400">
      {message} Check that the backend is running and reachable, then reload this page.
    </p>
  );
}
