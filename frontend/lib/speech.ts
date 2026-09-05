/**
 * Browser-native speech I/O used only in local/mock mode as a stand-in for
 * real audio transport, so the live-simulation UI is fully exercisable
 * before ASSEMBLYAI_API_KEY is wired up. This is NOT AssemblyAI — no
 * transcription-accuracy or pronunciation claims should ever be attached to
 * output from these APIs. When VOICE_AGENT_PROVIDER=assemblyai lands, mic
 * audio should be streamed to the backend instead of using SpeechRecognition
 * here, and this file's speak() helper can be dropped once TTS also comes
 * from the backend.
 */

interface MinimalSpeechRecognitionResult {
  0: { transcript: string };
  isFinal: boolean;
}

interface MinimalSpeechRecognitionEvent {
  results: ArrayLike<MinimalSpeechRecognitionResult>;
}

interface MinimalSpeechRecognition extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start(): void;
  stop(): void;
  onresult: ((event: MinimalSpeechRecognitionEvent) => void) | null;
  onerror: ((event: unknown) => void) | null;
  onend: (() => void) | null;
}

type SpeechRecognitionConstructor = new () => MinimalSpeechRecognition;

function getSpeechRecognitionConstructor(): SpeechRecognitionConstructor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export function isSpeechRecognitionSupported(): boolean {
  return getSpeechRecognitionConstructor() !== null;
}

export function isSpeechSynthesisSupported(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

export interface RecognitionHandle {
  stop: () => void;
}

/**
 * Starts continuous speech recognition. Calls onFinalResult with each
 * finalized utterance. Returns a handle to stop listening.
 */
export function startListening(
  languageTag: string,
  onFinalResult: (text: string) => void,
  onError?: (message: string) => void
): RecognitionHandle {
  const Recognition = getSpeechRecognitionConstructor();
  if (!Recognition) {
    onError?.("Speech recognition is not supported in this browser.");
    return { stop: () => {} };
  }

  const recognition = new Recognition();
  recognition.continuous = true;
  recognition.interimResults = false;
  recognition.lang = languageTag;

  recognition.onresult = (event) => {
    const results = event.results;
    const last = results[results.length - 1];
    if (last?.isFinal) {
      const transcript = last[0].transcript.trim();
      if (transcript) onFinalResult(transcript);
    }
  };

  recognition.onerror = (event) => {
    const err = event as { error?: string };
    onError?.(err.error ?? "Unknown speech recognition error");
  };

  recognition.onend = () => {
    recognition.start();
  };

  recognition.start();

  return {
    stop: () => {
      recognition.onend = null;
      recognition.stop();
    },
  };
}

export function speak(text: string, languageTag: string, onEnd?: () => void): void {
  if (!isSpeechSynthesisSupported()) {
    onEnd?.();
    return;
  }
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = languageTag;
  if (onEnd) utterance.onend = onEnd;
  window.speechSynthesis.speak(utterance);
}

export function languageTag(targetLanguage: "English" | "German"): string {
  return targetLanguage === "German" ? "de-DE" : "en-US";
}
