import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Nhận diện giọng nói tiếng Việt bằng Web Speech API của trình duyệt.
 *
 * `continuous = true` để người dùng nói thoải mái, ngập ngừng giữa câu không bị cắt. Nhưng
 * Chrome VẪN tự kết thúc phiên sau một quãng im lặng dù đã bật cờ này, nên hook phải tự mở phiên
 * mới và tự gom text qua các phiên — đó là phần lớn độ phức tạp ở đây. Xem
 * `docs/plan/voice-input-webspeech-plan.md`.
 *
 * Hai tầng chống mất/nhân đôi chữ:
 * - Trong một phiên: `transcript` được dựng LẠI từ đầu mỗi lần `onresult` thay vì cộng dồn.
 *   `event.results` là danh sách tích luỹ nên đọc lại luôn ra chuỗi đúng, miễn nhiễm với việc
 *   một result bị phát lại lúc chuyển từ interim sang final.
 * - Giữa các phiên: `event.results` reset về rỗng mỗi lần mở phiên mới, nên text của phiên cũ
 *   phải được chốt vào `committedRef` trước, nếu không phiên sau sẽ đè mất phiên trước.
 */

const LISTEN_LANG = "vi-VN";

/** Mic mở quên tắt cả buổi là chuyện riêng tư — trình duyệt vẫn đang nghe và gửi đi. */
const MAX_LISTEN_MS = 60_000;

/**
 * Một phiên thật không bao giờ kết thúc nhanh đến vậy — ngắn hơn ngưỡng này nghĩa là engine
 * không mở được. Không chặn thì vòng mở-phiên-mới quay tít, đốt CPU và nã liên tục vào dịch vụ
 * nhận diện của trình duyệt.
 */
const MIN_SESSION_MS = 300;

/** Ghép các mẩu text bằng đúng một khoảng trắng, bỏ qua mẩu rỗng. */
export function joinText(...parts: string[]): string {
  return parts.filter(Boolean).join(" ");
}

/** Firefox không có API này; Chrome/Edge/Safari chỉ có bản `webkit`. */
function getRecognitionConstructor(): SpeechRecognitionConstructor | undefined {
  return window.SpeechRecognition ?? window.webkitSpeechRecognition;
}

/** `no-speech` và `aborted` không tới đây — xem `onerror` bên dưới. */
function errorMessage(code: SpeechRecognitionErrorCode): string {
  if (code === "not-allowed" || code === "service-not-allowed") {
    return "Bạn cần cho phép dùng micro trong trình duyệt.";
  }
  if (code === "audio-capture") {
    return "Không tìm thấy micro. Bạn kiểm tra lại thiết bị nhé.";
  }
  return "Không nhận diện được giọng nói. Bạn thử lại nhé.";
}

export function useSpeechRecognition() {
  /**
   * Tính trong thân hook chứ KHÔNG ở module scope: ở module scope thì giá trị bị chốt ngay lúc
   * `import`, test gỡ `window.SpeechRecognition` ra sẽ không có tác dụng.
   */
  const supported = Boolean(getRecognitionConstructor());
  const [listening, setListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [error, setError] = useState<string | null>(null);

  const recognitionRef = useRef<SpeechRecognition | null>(null);
  /** Ý định của người dùng — khác với trạng thái engine, vốn tự tắt bật liên tục. */
  const wantListeningRef = useRef(false);
  /** Text đã chốt của các phiên TRƯỚC trong cùng một lần bấm mic. */
  const committedRef = useRef("");
  const sessionTextRef = useRef("");
  const sessionStartedAtRef = useRef(0);
  const autoStopTimerRef = useRef<number | undefined>(undefined);

  const finish = useCallback(() => {
    window.clearTimeout(autoStopTimerRef.current);
    autoStopTimerRef.current = undefined;
    setListening(false);
  }, []);

  const beginSession = useCallback<() => void>(() => {
    const Recognition = getRecognitionConstructor();
    if (!Recognition) return;

    const recognition = new Recognition();
    recognition.lang = LISTEN_LANG;
    recognition.continuous = true;
    recognition.interimResults = true;

    recognition.onresult = (event) => {
      let text = "";
      for (let i = 0; i < event.results.length; i += 1) {
        text += event.results[i][0].transcript;
      }
      sessionTextRef.current = text;
      setTranscript(joinText(committedRef.current, text));
    };

    /**
     * `no-speech` chỉ là im lặng quá lâu — bỏ qua để `onend` mở phiên mới, nếu không mỗi lần
     * người dùng ngập ngừng là UI nhảy báo lỗi. Mọi mã còn lại đều là hỏng thật, phải tắt ý định
     * nghe: mở lại phiên chỉ khiến nó hỏng y hệt, thành vòng lặp vô hạn. `aborted` là do chính
     * ta gọi `abort()` nên tắt mà không báo gì.
     */
    recognition.onerror = (event) => {
      if (event.error === "no-speech") return;
      wantListeningRef.current = false;
      if (event.error !== "aborted") setError(errorMessage(event.error));
    };

    recognition.onend = () => {
      committedRef.current = joinText(committedRef.current, sessionTextRef.current);
      sessionTextRef.current = "";

      if (!wantListeningRef.current) {
        finish();
        return;
      }
      if (Date.now() - sessionStartedAtRef.current < MIN_SESSION_MS) {
        setError("Không nghe được từ micro. Bạn kiểm tra lại thiết bị nhé.");
        finish();
        return;
      }
      beginSession();
    };

    recognitionRef.current = recognition;
    sessionStartedAtRef.current = Date.now();
    recognition.start();
  }, [finish]);

  /**
   * Tắt `listening` ngay chứ không chờ `onend`: ô nhập mở khoá tức thì, không có trạng thái kẹt
   * nếu `onend` không bao giờ tới. Chữ cuối vẫn không mất — `stop()` còn trả thêm một `onresult`
   * nữa, và `transcript` vẫn nhận nó bình thường sau khi `listening` đã tắt.
   */
  const stop = useCallback(() => {
    wantListeningRef.current = false;
    recognitionRef.current?.stop();
    finish();
  }, [finish]);

  const start = useCallback(() => {
    committedRef.current = "";
    sessionTextRef.current = "";
    wantListeningRef.current = true;
    setError(null);
    setTranscript("");
    setListening(true);
    autoStopTimerRef.current = window.setTimeout(stop, MAX_LISTEN_MS);
    beginSession();
  }, [beginSession, stop]);

  /** Rời trang khi đang nghe thì mic phải tắt hẳn. Gỡ handler trước để không mở lại phiên. */
  useEffect(() => {
    return () => {
      window.clearTimeout(autoStopTimerRef.current);
      wantListeningRef.current = false;
      const recognition = recognitionRef.current;
      if (!recognition) return;
      recognition.onresult = null;
      recognition.onerror = null;
      recognition.onend = null;
      recognition.abort();
    };
  }, []);

  return { supported, listening, transcript, error, start, stop };
}
