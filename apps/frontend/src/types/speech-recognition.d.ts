/**
 * Web Speech API (`SpeechRecognition`) — `lib.dom.d.ts` của TypeScript 5.9 CHƯA khai báo, nên
 * phải tự khai ở đây, nếu không `npm run typecheck` gãy.
 *
 * Chỉ khai báo phần `useSpeechRecognition` thật sự dùng, không chép cả spec vào. Riêng union mã
 * lỗi giữ đủ 8 giá trị của spec vì đó là miền giá trị thật của `error`, cắt bớt là khai báo sai.
 *
 * Cố ý KHÔNG khai báo `declare var SpeechRecognition`: Firefox không có API này, khai báo như
 * biến toàn cục là nói dối TS rằng nó luôn tồn tại. Chỉ mở qua `Window` để mọi nơi truy cập đều
 * buộc phải xử lý `undefined`.
 */

interface SpeechRecognitionAlternative {
  readonly transcript: string;
}

interface SpeechRecognitionResult {
  readonly [index: number]: SpeechRecognitionAlternative;
}

interface SpeechRecognitionResultList {
  readonly length: number;
  readonly [index: number]: SpeechRecognitionResult;
}

interface SpeechRecognitionEvent extends Event {
  readonly results: SpeechRecognitionResultList;
}

type SpeechRecognitionErrorCode =
  | "no-speech"
  | "aborted"
  | "audio-capture"
  | "network"
  | "not-allowed"
  | "service-not-allowed"
  | "bad-grammar"
  | "language-not-supported";

interface SpeechRecognitionErrorEvent extends Event {
  readonly error: SpeechRecognitionErrorCode;
}

interface SpeechRecognition extends EventTarget {
  lang: string;
  /** `false` = engine tự kết thúc phiên sau câu đầu tiên. Cả thiết kế MVP dựa trên điều này. */
  continuous: boolean;
  interimResults: boolean;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
}

type SpeechRecognitionConstructor = new () => SpeechRecognition;

interface Window {
  SpeechRecognition?: SpeechRecognitionConstructor;
  webkitSpeechRecognition?: SpeechRecognitionConstructor;
}
