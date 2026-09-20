"use client";

import { use, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { fetchScenario, WS_BASE_URL } from "@/lib/api";
import {
  isMicStreamingSupported,
  startAudioPlayer,
  startMicStreaming,
  type AudioPlayerHandle,
  type MicStreamHandle,
} from "@/lib/audioStream";
import { getStoredHintLanguage } from "@/lib/hintLanguage";
import type { EvaluationResult, Scenario, SessionEndPayload, Transcript, Turn } from "@/lib/types";

type Status = "loading" | "connecting" | "in_progress" | "ended" | "error";

export default function SimulatePage({
  params,
}: {
  params: Promise<{ scenarioId: string }>;
}) {
  const { scenarioId } = use(params);

  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [status, setStatus] = useState<Status>("loading");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [aiSpeaking, setAiSpeaking] = useState(false);
  const [listening, setListening] = useState(false);
  const [micArmed, setMicArmed] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [draft, setDraft] = useState("");
  const [finalTranscript, setFinalTranscript] = useState<Transcript | null>(null);
  const [evaluation, setEvaluation] = useState<EvaluationResult | null>(null);
  const [recommendedScenario, setRecommendedScenario] = useState<Scenario | null>(null);
  const [endRequested, setEndRequested] = useState(false);
  const [latestComplication, setLatestComplication] = useState<string | null>(null);
  const [latestHint, setLatestHint] = useState<{ term: string; translation: string; level: number } | null>(
    null,
  );
  const [latestGrammarHint, setLatestGrammarHint] = useState<string | null>(null);

  const socketRef = useRef<WebSocket | null>(null);
  const micHandleRef = useRef<MicStreamHandle | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const playerRef = useRef<AudioPlayerHandle | null>(null);
  const aiSpeakingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const transcriptEndRef = useRef<HTMLDivElement>(null);

  const micStreamingSupported = isMicStreamingSupported();

  const sendUserText = useCallback((text: string) => {
    const trimmed = text.trim();
    if (!trimmed || !socketRef.current || socketRef.current.readyState !== WebSocket.OPEN) return;
    setTurns((prev) => [...prev, { turn_index: prev.length, speaker: "learner", text: trimmed }]);
    socketRef.current.send(JSON.stringify({ type: "user_text", text: trimmed }));
  }, []);

  const teardownAudio = useCallback(() => {
    micHandleRef.current?.stop();
    playerRef.current?.close();
    audioContextRef.current?.close().catch(() => {});
    if (aiSpeakingTimeoutRef.current) clearTimeout(aiSpeakingTimeoutRef.current);
  }, []);

  // Load scenario details for the header.
  useEffect(() => {
    let cancelled = false;
    fetchScenario(scenarioId)
      .then((s) => {
        if (!cancelled) setScenario(s);
      })
      .catch(() => {
        if (!cancelled) {
          setStatus("error");
          setErrorMessage(`Couldn't load scenario '${scenarioId}'.`);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [scenarioId]);

  // Open the conversation WebSocket once the scenario is known.
  useEffect(() => {
    if (!scenario) return;

    const socket = new WebSocket(`${WS_BASE_URL}/ws/conversation`);
    socket.binaryType = "arraybuffer";
    socketRef.current = socket;

    socket.onopen = () => {
      setStatus("connecting");
      const hintLanguage = getStoredHintLanguage() ?? "English";
      socket.send(JSON.stringify({ type: "start", scenario_id: scenario.id, hint_language: hintLanguage }));
    };

    socket.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) {
        playerRef.current?.enqueue(event.data);
        setAiSpeaking(true);
        if (aiSpeakingTimeoutRef.current) clearTimeout(aiSpeakingTimeoutRef.current);
        aiSpeakingTimeoutRef.current = setTimeout(() => setAiSpeaking(false), 600);
        return;
      }

      const message = JSON.parse(event.data);

      if (message.type === "session_ready") {
        setStatus("in_progress");
      } else if (message.type === "agent_text") {
        setTurns((prev) => [...prev, { turn_index: message.turn_index, speaker: "ai", text: message.text }]);
      } else if (message.type === "user_transcript") {
        setTurns((prev) => [
          ...prev,
          { turn_index: message.turn_index, speaker: "learner", text: message.text },
        ]);
      } else if (message.type === "clear_audio") {
        playerRef.current?.clear();
        setAiSpeaking(false);
      } else if (message.type === "complication") {
        setLatestComplication(message.text);
      } else if (message.type === "hint") {
        setLatestHint({ term: message.term, translation: message.translation, level: message.level });
      } else if (message.type === "grammar_hint") {
        setLatestGrammarHint(message.note);
      } else if (message.type === "session_end") {
        const payload = message as SessionEndPayload;
        setFinalTranscript(payload.transcript);
        setEvaluation(payload.evaluation ?? null);
        setStatus("ended");
        setListening(false);
        teardownAudio();
        if (payload.error) setErrorMessage(payload.error);
        if (payload.recommended_scenario_id) {
          fetchScenario(payload.recommended_scenario_id).then(setRecommendedScenario).catch(() => {});
        }
      } else if (message.type === "error") {
        setErrorMessage(message.message);
        // A protocol error before the session even started (e.g. an unknown
        // scenario id) is recoverable by just retrying; an error once the
        // session is live means the voice-agent connection is broken and
        // nothing further will work, so stop pretending the UI is usable.
        // teardownAudio() is a safe no-op if the mic was never armed.
        setStatus((prev) => (prev === "connecting" || prev === "in_progress" ? "error" : prev));
        teardownAudio();
      }
    };

    socket.onerror = () => {
      setStatus((prev) => (prev === "ended" ? prev : "error"));
      setErrorMessage("Connection to the backend was lost.");
      teardownAudio();
    };

    return () => {
      teardownAudio();
      socket.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scenario]);

  // Elapsed-time ticker.
  useEffect(() => {
    if (status !== "in_progress" && status !== "connecting") return;
    const interval = setInterval(() => setElapsedSeconds((s) => s + 1), 1000);
    return () => clearInterval(interval);
  }, [status]);

  // Keep the newest message in view as the conversation grows.
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ block: "end" });
  }, [turns]);

  const armMicStreaming = async () => {
    if (!micStreamingSupported || !socketRef.current) return;
    try {
      const { context, handle } = await startMicStreaming(
        (chunk) => {
          if (socketRef.current?.readyState === WebSocket.OPEN) {
            socketRef.current.send(chunk);
          }
        },
        (msg) => setErrorMessage(msg)
      );
      audioContextRef.current = context;
      micHandleRef.current = handle;
      playerRef.current = startAudioPlayer(context);
      setMicArmed(true);
      setListening(true);
    } catch {
      // error already reported via onError callback
    }
  };

  const endSession = () => {
    setEndRequested(true);
    socketRef.current?.send(JSON.stringify({ type: "end" }));
  };

  const minutes = String(Math.floor(elapsedSeconds / 60)).padStart(2, "0");
  const seconds = String(elapsedSeconds % 60).padStart(2, "0");

  if (status === "loading") {
    return <p className="text-black/60 dark:text-white/60">Loading scenario…</p>;
  }

  if (status === "error" && !scenario) {
    return (
      <div className="flex flex-col gap-3">
        <p className="text-red-600 dark:text-red-400">{errorMessage}</p>
        <Link href="/scenarios" className="text-sm underline">
          Back to missions
        </Link>
      </div>
    );
  }

  const needsMicArm = !micArmed && status !== "ended" && status !== "error";

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">{scenario?.title}</h1>
          {scenario?.description && (
            <p className="mt-1 text-sm text-black/60 dark:text-white/60">{scenario.description}</p>
          )}
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-black/50 dark:text-white/50">
            <span>Your role: {scenario?.learner_role}</span>
            <span>AI plays: {scenario?.ai_role}</span>
          </div>
        </div>
        <div className="shrink-0 text-right text-sm text-black/60 dark:text-white/60">
          <div>{minutes}:{seconds}</div>
          <div className="mt-1 flex items-center justify-end gap-1.5">
            <span
              className={`h-2 w-2 rounded-full ${
                aiSpeaking ? "bg-blue-500" : listening ? "animate-pulse bg-green-500" : "bg-black/20 dark:bg-white/20"
              }`}
            />
            {aiSpeaking ? "AI speaking" : listening ? "Listening" : status === "ended" ? "Ended" : "Idle"}
          </div>
        </div>
      </div>

      {errorMessage && (
        <p className="rounded-md border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-600 dark:text-red-400">
          {errorMessage}
        </p>
      )}

      {latestComplication && status === "in_progress" && (
        <p className="rounded-md border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-700 dark:text-amber-400">
          ⚡ Things just changed: {latestComplication}
        </p>
      )}

      {latestHint && status === "in_progress" && (
        <p className="rounded-md border border-sky-500/30 bg-sky-500/10 px-4 py-3 text-sm text-sky-700 dark:text-sky-400">
          💡 Hint (level {latestHint.level}) — &ldquo;{latestHint.term}&rdquo; → {latestHint.translation}
        </p>
      )}

      {latestGrammarHint && status === "in_progress" && (
        <p className="rounded-md border border-violet-500/30 bg-violet-500/10 px-4 py-3 text-sm text-violet-700 dark:text-violet-400">
          ✏️ Grammar note — {latestGrammarHint}
        </p>
      )}

      {needsMicArm && (
        <div className="flex items-center justify-between rounded-md border border-black/10 px-4 py-3 dark:border-white/10">
          <p className="text-sm text-black/60 dark:text-white/60">
            {micStreamingSupported
              ? "Start your microphone to begin the live conversation."
              : "Microphone streaming isn't supported in this browser — type your responses below instead."}
          </p>
          {micStreamingSupported && (
            <button
              onClick={armMicStreaming}
              className="rounded-md bg-black px-4 py-2 text-sm font-medium text-white hover:bg-black/80 dark:bg-white dark:text-black dark:hover:bg-white/80"
            >
              Start speaking
            </button>
          )}
        </div>
      )}

      <div className="flex h-[28rem] flex-col justify-end gap-3 overflow-y-auto rounded-lg border border-black/10 p-4 dark:border-white/10">
        {turns.length === 0 && (
          <p className="text-sm text-black/40 dark:text-white/40">Waiting for the conversation to start…</p>
        )}
        {turns.map((turn) => (
          <div
            key={turn.turn_index}
            className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
              turn.speaker === "ai"
                ? "self-start bg-black/5 dark:bg-white/10"
                : "self-end bg-black text-white dark:bg-white dark:text-black"
            }`}
          >
            {turn.text}
          </div>
        ))}
        <div ref={transcriptEndRef} />
      </div>

      {status !== "ended" && status !== "error" && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            sendUserText(draft);
            setDraft("");
          }}
          className="flex gap-2"
        >
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Type your response…"
            className="flex-1 rounded-md border border-black/10 px-3 py-2 text-sm dark:border-white/10 dark:bg-transparent"
          />
          <button
            type="submit"
            className="rounded-md border border-black/10 px-4 py-2 text-sm dark:border-white/10"
          >
            Send
          </button>
          <button
            type="button"
            onClick={endSession}
            disabled={endRequested}
            className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
          >
            {endRequested ? "Ending…" : "End"}
          </button>
        </form>
      )}

      {status === "error" && (
        <div className="flex gap-3">
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="rounded-md bg-black px-4 py-2 text-sm font-medium text-white hover:bg-black/80 dark:bg-white dark:text-black dark:hover:bg-white/80"
          >
            Retry this mission
          </button>
          <Link href="/scenarios" className="rounded-md border border-black/10 px-4 py-2 text-sm dark:border-white/10">
            Back to missions
          </Link>
        </div>
      )}

      {status === "ended" && endRequested && !evaluation && !errorMessage && (
        <p className="text-sm text-black/60 dark:text-white/60">Evaluating your conversation…</p>
      )}

      {status === "ended" && !evaluation && errorMessage && (
        <Link href="/scenarios" className="text-sm underline">
          Back to missions
        </Link>
      )}

      {status === "ended" && evaluation && (
        <FeedbackPanel
          evaluation={evaluation}
          recommendedScenario={recommendedScenario}
          turnCount={finalTranscript?.turns.length ?? 0}
        />
      )}
    </div>
  );
}

function ScoreRow({ label, score }: { label: string; score: number }) {
  return (
    <div className="flex items-center gap-3">
      <span className="w-40 shrink-0 text-sm text-black/60 dark:text-white/60">{label}</span>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-black/10 dark:bg-white/10">
        <div className="h-full rounded-full bg-black dark:bg-white" style={{ width: `${score}%` }} />
      </div>
      <span className="w-12 shrink-0 text-right text-sm tabular-nums">{(score / 10).toFixed(1)}/10</span>
    </div>
  );
}

function FeedbackPanel({
  evaluation,
  recommendedScenario,
  turnCount,
}: {
  evaluation: EvaluationResult;
  recommendedScenario: Scenario | null;
  turnCount: number;
}) {
  return (
    <div className="flex flex-col gap-5 rounded-lg border border-black/10 p-5 dark:border-white/10">
      <div>
        <h2 className="text-lg font-semibold">Simulation Coach debrief</h2>
        <p className="text-sm text-black/60 dark:text-white/60">
          {turnCount} turns · overall {(evaluation.overall_score / 10).toFixed(1)}/10
        </p>
      </div>

      <div className="flex flex-col gap-2">
        <ScoreRow label="Grammar" score={evaluation.grammar} />
        <ScoreRow label="Vocabulary" score={evaluation.vocabulary} />
        <ScoreRow label="Fluency" score={evaluation.fluency} />
        <ScoreRow label="Hesitation" score={evaluation.hesitation} />
        <ScoreRow label="Task completion" score={evaluation.task_completion} />
        <ScoreRow label="Conversation handling" score={evaluation.conversation_handling} />
        <ScoreRow label="Handling surprises" score={evaluation.communication_recovery} />
      </div>
      <p className="text-xs text-black/40 dark:text-white/40">
        &quot;Handling surprises&quot; is about recovering when the conversation didn&apos;t go
        as expected — clarifying, rephrasing, adapting — not pronunciation. Pronunciation isn&apos;t
        scored: that needs real acoustic/phoneme analysis, which this evaluator (working from the
        text transcript only) can&apos;t honestly provide.
      </p>

      {evaluation.strengths.length > 0 && (
        <div>
          <h3 className="text-sm font-medium">What you did well</h3>
          <ul className="mt-1 list-inside list-disc text-sm text-black/70 dark:text-white/70">
            {evaluation.strengths.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </div>
      )}

      {evaluation.weaknesses.length > 0 && (
        <div>
          <h3 className="text-sm font-medium">Areas to improve</h3>
          <ul className="mt-1 list-inside list-disc text-sm text-black/70 dark:text-white/70">
            {evaluation.weaknesses.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex items-center justify-between border-t border-black/10 pt-4 dark:border-white/10">
        <Link href="/scenarios" className="text-sm underline">
          Browse all missions
        </Link>
        {recommendedScenario && (
          <Link
            href={`/simulate/${recommendedScenario.id}`}
            className="rounded-md bg-black px-4 py-2 text-sm font-medium text-white hover:bg-black/80 dark:bg-white dark:text-black dark:hover:bg-white/80"
          >
            Try this next: {recommendedScenario.title}
          </Link>
        )}
      </div>
    </div>
  );
}
