import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertCircle,
  ChevronDown,
  History as HistoryIcon,
  Mic,
  Sparkles,
  Trash2,
  Volume2,
  X,
} from "lucide-react";
import { useTranslate } from "@workspace/api-client-react";
import { useToast } from "./components/ui/use-toast";

type Lang = "en-US" | "ar-SA";
type Status = "idle" | "listening" | "translating" | "speaking" | "error";

interface Exchange {
  id: string;
  speaker: Lang;
  original: string;
  translated: string;
  timestamp: number;
}

const LANG_META: Record<Lang, { label: string; short: string; dir: "ltr" | "rtl"; isArabic: boolean }> = {
  "en-US": { label: "English", short: "EN", dir: "ltr", isArabic: false },
  "ar-SA": { label: "Arabic", short: "AR", dir: "rtl", isArabic: true },
};

function oppositeLang(lang: Lang): Lang {
  return lang === "en-US" ? "ar-SA" : "en-US";
}

function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString("en-GB", { hour12: false });
}

export default function Interpreter() {
  const { toast } = useToast();

  // --- State ---
  const [status, setStatusState] = useState<Status>("idle");
  const [activeSpeaker, setActiveSpeakerState] = useState<Lang | null>(null);
  const [interimText, setInterimText] = useState("");
  const [latestExchange, setLatestExchange] = useState<Exchange | null>(null);
  const [history, setHistory] = useState<Exchange[]>([]);
  const [historyOpen, setHistoryOpen] = useState(false);

  // --- Refs that mirror state, so SpeechRecognition handlers never read stale closures ---
  const statusRef = useRef<Status>("idle");
  const activeSpeakerRef = useRef<Lang | null>(null);
  const finalTranscriptRef = useRef("");

  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const synthRef = useRef<SpeechSynthesis | null>(
    typeof window !== "undefined" ? window.speechSynthesis : null,
  );
  const voicesRef = useRef<SpeechSynthesisVoice[]>([]);
  const supportedRef = useRef(true);
  const historyEndRef = useRef<HTMLDivElement | null>(null);

  // Synced setters — always update ref + state together.
  const setStatus = useCallback((next: Status) => {
    statusRef.current = next;
    setStatusState(next);
  }, []);
  const setActiveSpeaker = useCallback((next: Lang | null) => {
    activeSpeakerRef.current = next;
    setActiveSpeakerState(next);
  }, []);

  const translate = useTranslate();

  // --- Text to speech ---
  const speak = useCallback(
    (text: string, lang: Lang) => {
      const synth = synthRef.current;
      if (!synth) {
        setStatus("idle");
        setActiveSpeaker(null);
        return;
      }
      synth.cancel();

      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = lang;
      utterance.rate = 1;
      utterance.pitch = 1;

      const voices = voicesRef.current.length ? voicesRef.current : synth.getVoices();
      const exact = voices.find((v) => v.lang === lang);
      const prefix = lang.split("-")[0];
      const partial = voices.find((v) => v.lang.toLowerCase().startsWith(prefix.toLowerCase()));
      const chosen = exact ?? partial;
      if (chosen) utterance.voice = chosen;

      utterance.onend = () => {
        setStatus("idle");
        setActiveSpeaker(null);
      };
      utterance.onerror = () => {
        setStatus("idle");
        setActiveSpeaker(null);
      };

      setStatus("speaking");
      synth.speak(utterance);
    },
    [setStatus, setActiveSpeaker],
  );

  // --- Translation ---
  const handleTranslation = useCallback(
    (text: string, speaker: Lang) => {
      const targetLang = oppositeLang(speaker);
      setStatus("translating");
      setInterimText("");

      translate.mutate(
        { data: { text, source: speaker, target: targetLang } },
        {
          onSuccess: (data) => {
            const translated = data.translation;
            const exchange: Exchange = {
              id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
              speaker,
              original: text,
              translated,
              timestamp: Date.now(),
            };
            setLatestExchange(exchange);
            setHistory((prev) => [...prev, exchange]);
            speak(translated, targetLang);
          },
          onError: (err: unknown) => {
            const message =
              err instanceof Error ? err.message : "Translation failed. Please try again.";
            toast({
              variant: "destructive",
              title: "Translation failed",
              description: message,
            });
            setStatus("error");
            setTimeout(() => {
              setStatus("idle");
              setActiveSpeaker(null);
            }, 2500);
          },
        },
      );
    },
    [translate, speak, toast, setStatus, setActiveSpeaker],
  );

  // Keep a stable ref to handleTranslation so the one-time recognition effect
  // can call the latest version without re-subscribing.
  const handleTranslationRef = useRef(handleTranslation);
  useEffect(() => {
    handleTranslationRef.current = handleTranslation;
  }, [handleTranslation]);

  // --- Speech recognition setup (runs once) ---
  useEffect(() => {
    // Load voices (may arrive asynchronously).
    const synth = synthRef.current;
    if (synth) {
      const loadVoices = () => {
        voicesRef.current = synth.getVoices();
      };
      loadVoices();
      synth.addEventListener?.("voiceschanged", loadVoices);
    }

    const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognitionAPI) {
      supportedRef.current = false;
      toast({
        variant: "destructive",
        title: "Browser not supported",
        description: "ASSISTRAN needs the Web Speech API. Please use Chrome or Edge.",
        duration: 8000,
      });
      return;
    }

    const recognition = new SpeechRecognitionAPI();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let interim = "";
      let final = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        const transcript = result[0].transcript;
        if (result.isFinal) {
          final += transcript;
        } else {
          interim += transcript;
        }
      }
      if (final) {
        finalTranscriptRef.current = (finalTranscriptRef.current + " " + final).trim();
      }
      setInterimText(finalTranscriptRef.current ? `${finalTranscriptRef.current} ${interim}`.trim() : interim);
    };

    recognition.onend = () => {
      // Translation is triggered HERE (after recognition fully ends), never on
      // button release — onend fires after the final onresult.
      const text = finalTranscriptRef.current.trim();
      const speaker = activeSpeakerRef.current;

      if (text && speaker) {
        handleTranslationRef.current(text, speaker);
      } else {
        // Only surface "no speech" if we were actually listening (ignore aborts
        // that already moved us out of the listening state).
        if (statusRef.current === "listening") {
          toast({
            title: "No speech detected",
            description: "Hold the button and speak clearly, then release.",
          });
        }
        setInterimText("");
        setStatus("idle");
        setActiveSpeaker(null);
      }
    };

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      const code = event.error;
      if (code === "aborted") {
        // Silent — typically a deliberate stop/cancel.
        return;
      }
      let description = "Something went wrong with speech recognition.";
      switch (code) {
        case "not-allowed":
        case "service-not-allowed":
          description = "Microphone permission was denied. Please allow mic access and try again.";
          break;
        case "no-speech":
          description = "No speech was detected. Hold the button and speak clearly.";
          break;
        case "network":
          description = "Network error during speech recognition. Check your connection.";
          break;
        case "audio-capture":
          description = "No microphone was found. Please connect a mic and try again.";
          break;
      }
      toast({ variant: "destructive", title: "Microphone error", description });
      finalTranscriptRef.current = "";
      setInterimText("");
      setStatus("idle");
      setActiveSpeaker(null);
    };

    recognitionRef.current = recognition;

    return () => {
      recognition.onresult = null;
      recognition.onend = null;
      recognition.onerror = null;
      try {
        recognition.abort();
      } catch {
        // ignore
      }
      if (synth) synth.removeEventListener?.("voiceschanged", () => {});
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --- PTT controls ---
  const startListening = useCallback(
    (speaker: Lang) => {
      if (statusRef.current !== "idle" && statusRef.current !== "error") return;
      const recognition = recognitionRef.current;
      if (!recognition) {
        if (!supportedRef.current) {
          toast({
            variant: "destructive",
            title: "Browser not supported",
            description: "ASSISTRAN needs the Web Speech API. Please use Chrome or Edge.",
          });
        }
        return;
      }

      // Cancel any ongoing speech before capturing.
      synthRef.current?.cancel();

      finalTranscriptRef.current = "";
      setInterimText("");
      setStatus("listening");
      setActiveSpeaker(speaker);
      recognition.lang = speaker;

      try {
        recognition.start();
      } catch {
        // start() throws if already started — reset state to recover.
        setStatus("idle");
        setActiveSpeaker(null);
      }
    },
    [toast, setStatus, setActiveSpeaker],
  );

  const stopListening = useCallback(() => {
    if (statusRef.current !== "listening") return;
    // Do NOT process the transcript here — onend handles it.
    recognitionRef.current?.stop();
  }, []);

  // --- Prevent the mobile long-press context menu ---
  useEffect(() => {
    const handler = (e: MouseEvent) => e.preventDefault();
    document.addEventListener("contextmenu", handler);
    return () => document.removeEventListener("contextmenu", handler);
  }, []);

  // --- Auto-scroll history to bottom when entries are added ---
  useEffect(() => {
    if (historyOpen) {
      historyEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [history.length, historyOpen]);

  const busy = status === "translating" || status === "speaking";
  const isRecording = status === "listening";
  const recordingEn = isRecording && activeSpeaker === "en-US";
  const recordingAr = isRecording && activeSpeaker === "ar-SA";

  return (
    <div className="relative flex h-full min-h-[100dvh] flex-col overflow-hidden bg-background text-foreground">
      {/* Ambient background */}
      <div className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
        <div className="absolute left-1/2 top-[-10%] h-[40rem] w-[40rem] -translate-x-1/2 rounded-full bg-primary/5 blur-[120px]" />
        <div className="absolute bottom-[-10%] left-1/2 h-[40rem] w-[40rem] -translate-x-1/2 rounded-full bg-secondary/5 blur-[120px]" />
      </div>

      {/* Header */}
      <header className="px-6 pt-8 text-center">
        <div className="flex items-center justify-center gap-2">
          <Sparkles className="h-6 w-6 text-primary" />
          <h1 className="text-3xl font-bold tracking-tight">ASSISTRAN</h1>
          <Sparkles className="h-6 w-6 text-secondary" />
        </div>
        <p className="mt-1 text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
          Two-Way AI Speech Translator
        </p>
        <p className="mt-2 text-sm text-muted-foreground">Speak. Translate. Respond.</p>
        <p dir="rtl" className="mt-1 text-sm text-muted-foreground">
          أسيستران — تحدث. ترجم. تواصل.
        </p>
      </header>

      {/* Status pill */}
      <div className="mt-6 flex justify-center">
        <StatusPill status={status} activeSpeaker={activeSpeaker} />
      </div>

      {/* Transcript / result area */}
      <main className="flex flex-1 items-center justify-center px-6">
        <div className="w-full max-w-2xl">
          <AnimatePresence mode="wait">
            {isRecording && interimText ? (
              <motion.div
                key="interim"
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -16 }}
                className="text-center"
              >
                <p
                  dir={activeSpeaker === "ar-SA" ? "rtl" : "ltr"}
                  className="text-2xl font-light italic leading-relaxed text-foreground/90 md:text-3xl"
                >
                  &ldquo;{interimText}&rdquo;
                </p>
              </motion.div>
            ) : latestExchange && !isRecording ? (
              <motion.div
                key={latestExchange.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="glass-card rounded-3xl p-6 md:p-8"
              >
                <ExchangeCard exchange={latestExchange} large />
              </motion.div>
            ) : (
              <motion.div
                key="empty"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="text-center text-muted-foreground"
              >
                <p className="text-lg">Hold a button and speak.</p>
                <p className="mt-1 text-sm">اضغط مع الاستمرار وتحدث</p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </main>

      {/* PTT controls */}
      <footer className="px-6 pb-10 pt-4">
        <div className="mx-auto flex max-w-md items-end justify-between gap-4">
          <PttButton
            lang="en-US"
            recording={recordingEn}
            disabled={busy || recordingAr}
            onStart={() => startListening("en-US")}
            onStop={stopListening}
          />

          <HistoryButton
            count={history.length}
            disabled={history.length === 0}
            onClick={() => setHistoryOpen(true)}
          />

          <PttButton
            lang="ar-SA"
            recording={recordingAr}
            disabled={busy || recordingEn}
            onStart={() => startListening("ar-SA")}
            onStop={stopListening}
          />
        </div>
      </footer>

      {/* History drawer */}
      <HistoryDrawer
        open={historyOpen}
        history={history}
        onClose={() => setHistoryOpen(false)}
        onClear={() => {
          setHistory([]);
          setHistoryOpen(false);
        }}
        endRef={historyEndRef}
      />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Status pill                                                         */
/* ------------------------------------------------------------------ */

function StatusPill({ status, activeSpeaker }: { status: Status; activeSpeaker: Lang | null }) {
  let content: React.ReactNode;

  if (status === "idle") {
    content = (
      <>
        <span className="h-2.5 w-2.5 rounded-full bg-muted-foreground" />
        <span className="text-xs font-semibold tracking-widest text-muted-foreground">READY</span>
      </>
    );
  } else if (status === "listening") {
    const isEn = activeSpeaker === "en-US";
    content = (
      <>
        <motion.span
          className={`h-2.5 w-2.5 rounded-full ${isEn ? "bg-primary" : "bg-secondary"}`}
          animate={{ scale: [1, 1.6, 1], opacity: [1, 0.5, 1] }}
          transition={{ duration: 1, repeat: Infinity }}
        />
        <span
          className={`text-xs font-semibold tracking-widest ${isEn ? "text-primary" : "text-secondary"}`}
        >
          LISTENING
        </span>
      </>
    );
  } else if (status === "translating") {
    content = (
      <>
        <motion.span
          animate={{ rotate: 360 }}
          transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
        >
          <Sparkles className="h-4 w-4 text-foreground" />
        </motion.span>
        <span className="shimmer-text text-xs font-semibold tracking-widest">TRANSLATING...</span>
      </>
    );
  } else if (status === "speaking") {
    // Opposite color from the speaker (we are emitting the other language).
    const speakingEn = activeSpeaker === "ar-SA"; // AR spoke -> EN output
    content = (
      <>
        <motion.span
          animate={{ scale: [1, 1.25, 1] }}
          transition={{ duration: 0.8, repeat: Infinity }}
        >
          <Volume2 className={`h-4 w-4 ${speakingEn ? "text-primary" : "text-secondary"}`} />
        </motion.span>
        <span
          className={`text-xs font-semibold tracking-widest ${speakingEn ? "text-primary" : "text-secondary"}`}
        >
          SPEAKING
        </span>
      </>
    );
  } else {
    content = (
      <>
        <AlertCircle className="h-4 w-4 text-[hsl(var(--destructive))]" />
        <span className="text-xs font-semibold tracking-widest text-[hsl(var(--destructive))]">
          ERROR
        </span>
      </>
    );
  }

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={status + (activeSpeaker ?? "")}
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.9 }}
        transition={{ duration: 0.2 }}
        className="glass-card flex items-center gap-2 rounded-full px-4 py-2"
      >
        {content}
      </motion.div>
    </AnimatePresence>
  );
}

/* ------------------------------------------------------------------ */
/* Exchange card (shared by latest result + history)                  */
/* ------------------------------------------------------------------ */

function ExchangeCard({ exchange, large = false }: { exchange: Exchange; large?: boolean }) {
  const src = LANG_META[exchange.speaker];
  const tgt = LANG_META[oppositeLang(exchange.speaker)];

  return (
    <div>
      <p
        className={`mb-2 text-xs font-semibold uppercase tracking-widest ${
          src.isArabic ? "text-secondary" : "text-primary"
        }`}
      >
        {src.label}
      </p>
      <p
        dir={src.dir}
        className={`${large ? "text-xl md:text-2xl" : "text-base"} font-medium text-foreground/90`}
      >
        {exchange.original}
      </p>

      <div className="my-4 flex items-center gap-3">
        <div className="h-px flex-1 bg-border" />
        <ChevronDown className="h-4 w-4 text-muted-foreground" />
        <div className="h-px flex-1 bg-border" />
      </div>

      <p
        className={`mb-2 text-xs font-semibold uppercase tracking-widest ${
          tgt.isArabic ? "text-secondary" : "text-primary"
        }`}
      >
        {tgt.label}
      </p>
      <p
        dir={tgt.dir}
        className={`${large ? "text-2xl md:text-3xl" : "text-lg"} font-semibold text-foreground`}
      >
        {exchange.translated}
      </p>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* PTT button                                                         */
/* ------------------------------------------------------------------ */

function PttButton({
  lang,
  recording,
  disabled,
  onStart,
  onStop,
}: {
  lang: Lang;
  recording: boolean;
  disabled: boolean;
  onStart: () => void;
  onStop: () => void;
}) {
  const meta = LANG_META[lang];
  const isEn = lang === "en-US";

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative">
        {/* Glow */}
        <motion.div
          className={`absolute inset-0 rounded-full blur-lg ${isEn ? "bg-primary/10" : "bg-secondary/10"}`}
          animate={{ scale: recording ? 1.25 : 1 }}
          transition={{ duration: 0.3 }}
        />

        {/* Ripple ring while recording */}
        <AnimatePresence>
          {recording && (
            <motion.span
              className={`absolute inset-0 rounded-full border-2 ${isEn ? "border-primary" : "border-secondary"}`}
              initial={{ scale: 1, opacity: 0.7 }}
              animate={{ scale: 1.6, opacity: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 1.2, repeat: Infinity, ease: "easeOut" }}
            />
          )}
        </AnimatePresence>

        <button
          type="button"
          disabled={disabled}
          aria-label={`Hold to speak ${meta.label}`}
          onMouseDown={onStart}
          onMouseUp={onStop}
          onMouseLeave={onStop}
          onTouchStart={(e) => {
            e.preventDefault();
            onStart();
          }}
          onTouchEnd={(e) => {
            e.preventDefault();
            onStop();
          }}
          className={`relative flex h-24 w-24 items-center justify-center rounded-full border-2 transition-all md:h-28 md:w-28 ${
            isEn ? "border-primary bg-primary/5" : "border-secondary bg-secondary/5"
          } ${disabled ? "cursor-not-allowed opacity-30" : "cursor-pointer active:scale-95"} ${
            recording ? (isEn ? "bg-primary/20" : "bg-secondary/20") : ""
          }`}
        >
          <motion.span
            animate={recording ? { scale: [1, 1.15, 1] } : { scale: 1 }}
            transition={{ duration: 0.8, repeat: recording ? Infinity : 0 }}
          >
            <Mic className={`h-9 w-9 ${isEn ? "text-primary" : "text-secondary"}`} />
          </motion.span>
        </button>
      </div>
      <span
        className={`text-xs font-bold tracking-widest ${isEn ? "text-primary" : "text-secondary"}`}
      >
        {meta.label.toUpperCase()}
      </span>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* History button                                                     */
/* ------------------------------------------------------------------ */

function HistoryButton({
  count,
  disabled,
  onClick,
}: {
  count: number;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <div className="flex flex-col items-center gap-2 pb-1">
      <button
        type="button"
        disabled={disabled}
        onClick={onClick}
        aria-label="Open session history"
        className={`relative flex h-12 w-12 items-center justify-center rounded-full border border-border bg-card transition-all ${
          disabled ? "cursor-not-allowed opacity-30" : "cursor-pointer hover:border-primary/50 active:scale-95"
        }`}
      >
        <HistoryIcon className="h-5 w-5 text-foreground" />
        {count > 0 && (
          <span className="absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-primary px-1 text-[10px] font-bold text-primary-foreground">
            {count}
          </span>
        )}
      </button>
      <span className="text-xs font-bold tracking-widest text-muted-foreground">HISTORY</span>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* History drawer                                                     */
/* ------------------------------------------------------------------ */

function HistoryDrawer({
  open,
  history,
  onClose,
  onClear,
  endRef,
}: {
  open: boolean;
  history: Exchange[];
  onClose: () => void;
  onClear: () => void;
  endRef: React.RefObject<HTMLDivElement | null>;
}) {
  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.div
            className="glass-card fixed inset-x-0 bottom-0 z-50 flex max-h-[80dvh] flex-col rounded-t-3xl"
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", stiffness: 320, damping: 32 }}
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-border px-5 py-4">
              <div className="flex items-center gap-2">
                <HistoryIcon className="h-5 w-5 text-primary" />
                <h2 className="text-base font-semibold">Session History</h2>
                <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-primary px-1.5 text-[11px] font-bold text-primary-foreground">
                  {history.length}
                </span>
              </div>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={onClear}
                  aria-label="Clear history"
                  className="rounded-lg p-2 text-muted-foreground transition-colors hover:text-[hsl(var(--destructive))]"
                >
                  <Trash2 className="h-5 w-5" />
                </button>
                <button
                  type="button"
                  onClick={onClose}
                  aria-label="Close history"
                  className="rounded-lg p-2 text-muted-foreground transition-colors hover:text-foreground"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
            </div>

            {/* List */}
            <div className="relative flex-1 overflow-y-auto px-4 py-4">
              <div className="flex flex-col gap-3">
                {history.map((exchange, i) => (
                  <motion.div
                    key={exchange.id}
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.03 }}
                    className="rounded-2xl border border-border bg-card/60 p-4"
                  >
                    <div className="mb-2 flex items-center justify-between">
                      <DirectionBadge speaker={exchange.speaker} />
                      <span className="text-[11px] tabular-nums text-muted-foreground">
                        {formatTime(exchange.timestamp)}
                      </span>
                    </div>
                    <p
                      dir={LANG_META[exchange.speaker].dir}
                      className="text-sm text-foreground/80"
                    >
                      {exchange.original}
                    </p>
                    <div className="my-2 flex items-center gap-2">
                      <div className="h-px flex-1 bg-border" />
                      <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                      <div className="h-px flex-1 bg-border" />
                    </div>
                    <p
                      dir={LANG_META[oppositeLang(exchange.speaker)].dir}
                      className="text-sm font-medium text-foreground"
                    >
                      {exchange.translated}
                    </p>
                  </motion.div>
                ))}
                <div ref={endRef} />
              </div>
              {/* Gradient fade at the bottom */}
              <div className="pointer-events-none sticky bottom-0 -mb-4 h-8 bg-gradient-to-t from-[hsl(var(--background))] to-transparent" />
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

function DirectionBadge({ speaker }: { speaker: Lang }) {
  const isEn = speaker === "en-US";
  const label = isEn ? "EN → AR" : "AR → EN";
  return (
    <span
      className={`rounded-md px-2 py-0.5 text-[11px] font-bold tracking-wide ${
        isEn ? "bg-primary/15 text-primary" : "bg-secondary/15 text-secondary"
      }`}
    >
      {label}
    </span>
  );
}
