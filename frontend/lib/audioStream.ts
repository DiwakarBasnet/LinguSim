/**
 * Raw PCM16 mono audio capture/playback for the real AssemblyAI Voice Agent
 * path. AssemblyAI's managed pipeline (wss://agents.assemblyai.com/v1/ws,
 * proxied through our backend) speaks PCM16 mono @ 24kHz in both
 * directions, sent/received as binary WebSocket frames — no separate STT/TTS
 * calls on our side. This is unrelated to lib/speech.ts, which is only used
 * for the mock provider.
 */

export const VOICE_AGENT_SAMPLE_RATE = 24000;
const CAPTURE_BUFFER_SIZE = 4096;

export interface MicStreamHandle {
  stop: () => void;
}

export function isMicStreamingSupported(): boolean {
  return (
    typeof window !== "undefined" &&
    !!navigator.mediaDevices?.getUserMedia &&
    "AudioContext" in window
  );
}

function floatTo16BitPCM(input: Float32Array): ArrayBuffer {
  const buffer = new ArrayBuffer(input.length * 2);
  const view = new DataView(buffer);
  for (let i = 0; i < input.length; i++) {
    const sample = Math.max(-1, Math.min(1, input[i]));
    view.setInt16(i * 2, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
  }
  return buffer;
}

/**
 * Starts streaming mic audio as PCM16 mono @ 24kHz chunks to onChunk.
 * The returned AudioContext is shared with startAudioPlayer so capture and
 * playback stay on one clock; call stop() to tear everything down.
 */
export async function startMicStreaming(
  onChunk: (chunk: ArrayBuffer) => void,
  onError?: (message: string) => void
): Promise<{ context: AudioContext; handle: MicStreamHandle }> {
  const context = new AudioContext({ sampleRate: VOICE_AGENT_SAMPLE_RATE });

  let stream: MediaStream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch {
    onError?.("Microphone access was denied or unavailable.");
    throw new Error("mic_permission_denied");
  }

  const source = context.createMediaStreamSource(stream);
  // ScriptProcessorNode is deprecated but has universal support and is
  // simple to reason about for a short-lived hackathon demo session.
  const processor = context.createScriptProcessor(CAPTURE_BUFFER_SIZE, 1, 1);

  processor.onaudioprocess = (event) => {
    const input = event.inputBuffer.getChannelData(0);
    onChunk(floatTo16BitPCM(input));
  };

  // ScriptProcessorNode only fires onaudioprocess while connected (directly
  // or indirectly) to the destination; route through a silent gain node so
  // the mic input is captured but never itself audible.
  const silentGain = context.createGain();
  silentGain.gain.value = 0;
  source.connect(processor);
  processor.connect(silentGain);
  silentGain.connect(context.destination);

  const handle: MicStreamHandle = {
    stop: () => {
      processor.disconnect();
      silentGain.disconnect();
      source.disconnect();
      stream.getTracks().forEach((track) => track.stop());
    },
  };

  return { context, handle };
}

export interface AudioPlayerHandle {
  enqueue: (chunk: ArrayBuffer) => void;
  clear: () => void;
  close: () => void;
}

/** Schedules incoming PCM16 mono @ 24kHz chunks for gapless playback. */
export function startAudioPlayer(context: AudioContext): AudioPlayerHandle {
  let nextStartTime = context.currentTime;
  let activeSources: AudioBufferSourceNode[] = [];

  const enqueue = (chunk: ArrayBuffer) => {
    const view = new DataView(chunk);
    const sampleCount = chunk.byteLength / 2;
    const floatData = new Float32Array(sampleCount);
    for (let i = 0; i < sampleCount; i++) {
      floatData[i] = view.getInt16(i * 2, true) / 0x8000;
    }

    const buffer = context.createBuffer(1, sampleCount, VOICE_AGENT_SAMPLE_RATE);
    buffer.copyToChannel(floatData, 0);

    const source = context.createBufferSource();
    source.buffer = buffer;
    source.connect(context.destination);

    const startAt = Math.max(nextStartTime, context.currentTime);
    source.start(startAt);
    nextStartTime = startAt + buffer.duration;

    activeSources.push(source);
    source.onended = () => {
      activeSources = activeSources.filter((s) => s !== source);
    };
  };

  const clear = () => {
    activeSources.forEach((source) => {
      try {
        source.stop();
      } catch {
        // already stopped
      }
    });
    activeSources = [];
    nextStartTime = context.currentTime;
  };

  return { enqueue, clear, close: clear };
}
