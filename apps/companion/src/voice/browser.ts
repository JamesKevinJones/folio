/* Browser Web Speech — free STT/TTS, no OpenAI required. */

type RecognitionLike = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start: () => void;
  stop: () => void;
  onresult: ((event: {
    resultIndex: number;
    results: ArrayLike<{ isFinal: boolean; 0: { transcript: string } }>;
  }) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
};

type RecognitionCtor = new () => RecognitionLike;

function getRecognitionCtor(): RecognitionCtor | null {
  const w = window as Window & {
    SpeechRecognition?: RecognitionCtor;
    webkitSpeechRecognition?: RecognitionCtor;
  };
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

export function browserVoiceSupported(): { stt: boolean; tts: boolean } {
  return {
    stt: Boolean(getRecognitionCtor()),
    tts: typeof window !== "undefined" && "speechSynthesis" in window,
  };
}

export function speakBrowser(text: string): Promise<void> {
  return new Promise((resolve) => {
    if (!("speechSynthesis" in window)) {
      resolve();
      return;
    }
    window.speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance(text.slice(0, 600));
    utter.rate = 1.05;
    utter.pitch = 1;
    const voices = window.speechSynthesis.getVoices();
    const preferred =
      voices.find((v) => /en-(US|GB|IN)/i.test(v.lang) && /female|zira|samantha|google/i.test(v.name)) ||
      voices.find((v) => /^en/i.test(v.lang));
    if (preferred) utter.voice = preferred;
    utter.onend = () => resolve();
    utter.onerror = () => resolve();
    window.speechSynthesis.speak(utter);
  });
}

export function createHoldToTalk(handlers: {
  onPartial?: (text: string) => void;
  onError?: (message: string) => void;
}): {
  start: () => void;
  stop: () => Promise<string>;
  supported: boolean;
} {
  const Ctor = getRecognitionCtor();
  if (!Ctor) {
    return {
      supported: false,
      start: () => undefined,
      stop: async () => "",
    };
  }

  let recognition: RecognitionLike | null = null;
  let finalText = "";
  let stopping: ((value: string) => void) | null = null;

  return {
    supported: true,
    start: () => {
      finalText = "";
      recognition = new Ctor();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = "en-US";
      recognition.onresult = (event) => {
        let interim = "";
        let finalized = "";
        for (let i = event.resultIndex; i < event.results.length; i += 1) {
          const piece = event.results[i][0]?.transcript || "";
          if (event.results[i].isFinal) finalized += piece;
          else interim += piece;
        }
        if (finalized) finalText = `${finalText} ${finalized}`.trim();
        handlers.onPartial?.((finalText || interim).trim());
      };
      recognition.onerror = (event) => {
        if (event.error !== "aborted" && event.error !== "no-speech") {
          handlers.onError?.(event.error);
        }
      };
      recognition.onend = () => {
        stopping?.(finalText.trim());
        stopping = null;
      };
      try {
        recognition.start();
      } catch {
        handlers.onError?.("Could not start microphone recognition");
      }
    },
    stop: () =>
      new Promise<string>((resolve) => {
        if (!recognition) {
          resolve(finalText.trim());
          return;
        }
        stopping = resolve;
        try {
          recognition.stop();
        } catch {
          resolve(finalText.trim());
        }
        window.setTimeout(() => {
          if (stopping) {
            stopping(finalText.trim());
            stopping = null;
          }
        }, 1200);
      }),
  };
}
