"use client";

import { use, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { fetchScenario, WS_BASE_URL } from "@/lib/api";
import {
  isSpeechRecognitionSupported,
  languageTag,
  speak,
  startListening,
  type RecognitionHandle,
} from "@/lib/speech";
import {
  isMicStreamingSupported,
  startAudioPlayer,
  startMicStreaming,
  type AudioPlayerHandle,
  type MicStreamHandle,
} from "@/lib/audioStream";
import type { EvaluationResult, Scenario, SessionEndPayload, Transcript, Turn } from "@/lib/types";

type Status = "loading" | "connecting" | "in_progress" | "ended" | "error";
type Mode = "mock" | "assemblyai" | null;

export default function SimulatePage({
  params,
}: {
  params: Promise<{ scenarioId: string }>;
}) {
  const { scenarioId } = use(params);

  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [status, setStatus] = useState<Status>("loading");
  const [mode, setMode] = useState<Mode>(null);
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

  const socketRef = useRef<WebSocket | null>(null);
  const modeRef = useRef<Mode>(null);
  const recognitionRef = useRef<RecognitionHandle | null>(null);
  const micHandleRef = useRef<MicStreamHandle | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const playerRef = useRef<AudioPlayerHandle | null>(null);
  const aiSpeakingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const browserSpeechSupported = isSpeechRecognitionSupported();
  const micStreamingSupported = isMicStreamingSupported();
  const langTag = scenario ? languageTag(scenario.target_language) : "en-US";

  const sendUserText = useCallback((text: string) => {
    const trimmed = text.trim();
    if (!trimmed || !socketRef.current || socketRef.current.readyState !== WebSocket.OPEN) return;
    setTurns((prev) => [...prev, { turn_index: prev.length, speaker: "learner", text: trimmed }]);
    socketRef.current.send(JSON.stringify({ type: "user_text", text: trimmed }));
  }, []);

  const teardownAudio = useCallback(() => {
    recognitionRef.current?.stop();
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
      socket.send(JSON.stringify({ type: "start", scenario_id: scenario.id }));
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
        modeRef.current = message.mode;
        setMode(message.mode);
        setStatus("in_progress");
      } else if (message.type === "agent_text") {
        setTurns((prev) => [...prev, { turn_index: message.turn_index, speaker: "ai", text: message.text }]);

        if (modeRef.current !== "assemblyai") {
          // Mock provider: no real audio stream, so speak it client-side and
          // only listen for the learner's reply once that finishes.
          recognitionRef.current?.stop();
          setListening(false);
          setAiSpeaking(true);
          speak(message.text, langTag, () => {
            setAiSpeaking(false);
            if (browserSpeechSupported) {
              recognitionRef.current = startListening(langTag, (text) => sendUserText(text), (msg) =>
                setErrorMessage(msg)
              );
              setListening(true);
            }
          });
        }
      } else if (message.type === "user_transcript") {
        setTurns((prev) => [
          ...prev,
          { turn_index: message.turn_index, speaker: "learner", text: message.text },
        ]);
      } else if (message.type === "clear_audio") {
        playerRef.current?.clear();
        setAiSpeaking(false);
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
      }
    };

    socket.onerror = () => {
      setStatus("error");
      setErrorMessage("Connection to the backend was lost.");
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
          Back to scenarios
        </Link>
      </div>
    );
  }

  const needsMicArm = mode === "assemblyai" && !micArmed && status !== "ended";

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">{scenario?.title}</h1>
          <p className="text-sm text-black/60 dark:text-white/60">
            You: {scenario?.learner_role} · AI: {scenario?.ai_role}
          </p>
        </div>
        <div className="text-right text-sm text-black/60 dark:text-white/60">
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

      {mode === "mock" && !browserSpeechSupported && status !== "ended" && (
        <p className="rounded-md border border-yellow-500/30 bg-yellow-500/10 px-4 py-3 text-sm text-yellow-700 dark:text-yellow-400">
          Your browser doesn&apos;t support speech recognition — type your responses below instead.
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

      <div className="flex min-h-64 flex-col gap-3 rounded-lg border border-black/10 p-4 dark:border-white/10">
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
      </div>

      {status !== "ended" && (
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

      {status === "ended" && endRequested && !evaluation && !errorMessage && (
        <p className="text-sm text-black/60 dark:text-white/60">Evaluating your conversation…</p>
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
        <h2 className="text-lg font-semibold">Session feedback</h2>
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
      </div>
      <p className="text-xs text-black/40 dark:text-white/40">
        Pronunciation isn&apos;t scored yet — that needs real acoustic/phoneme analysis, which
        this evaluator (working from the text transcript only) can&apos;t honestly provide.
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
          Browse all scenarios
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
