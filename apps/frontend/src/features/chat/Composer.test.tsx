// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Composer } from "@/features/chat/Composer";

/**
 * jsdom không có `SpeechRecognition` nên phải cắm bản giả vào `window` trước khi render.
 *
 * `stop()` ở đây CỐ Ý không gọi `onend`: engine thật kết thúc bất đồng bộ và còn trả thêm một
 * `onresult` sau lời gọi. Fake đồng bộ sẽ xanh cả trên bản code chốt text ngay lúc bấm dừng —
 * đúng cái bug ca "chữ cuối" bên dưới canh.
 */
class FakeRecognition {
  static instances: FakeRecognition[] = [];

  // Cố ý đặt NGƯỢC với cấu hình hook cần, để ca "cấu hình engine" chứng minh hook có ghi đè thật.
  lang = "";
  continuous = false;
  interimResults = false;
  onresult: ((event: SpeechRecognitionEvent) => void) | null = null;
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null = null;
  onend: (() => void) | null = null;
  stopCount = 0;
  abortCount = 0;

  constructor() {
    FakeRecognition.instances.push(this);
  }

  start() {}

  stop() {
    this.stopCount += 1;
  }

  abort() {
    this.abortCount += 1;
  }

  /** Mỗi tham số là transcript của một result trong danh sách tích luỹ của PHIÊN hiện tại. */
  emitResults(...transcripts: string[]) {
    const results = transcripts.map((transcript) => [{ transcript }]);
    act(() => {
      this.onresult?.({ results } as unknown as SpeechRecognitionEvent);
    });
  }

  emitError(code: SpeechRecognitionErrorCode) {
    act(() => {
      this.onerror?.({ error: code } as unknown as SpeechRecognitionErrorEvent);
    });
  }

  emitEnd() {
    act(() => {
      this.onend?.();
    });
  }
}

function lastRecognition(): FakeRecognition {
  const instance = FakeRecognition.instances.at(-1);
  if (!instance) throw new Error("Chưa có SpeechRecognition nào được tạo");
  return instance;
}

const micButton = () => screen.getByRole("button", { name: /Nói|Dừng nói/ });
const sendButton = () => screen.getByRole("button", { name: "Gửi" });
const textarea = () => screen.getByRole("textbox");

/** Hook so `Date.now()` để biết phiên có đóng bất thường nhanh không — test phải lái được nó. */
let clockMs = 0;

beforeEach(() => {
  FakeRecognition.instances = [];
  clockMs = 1_700_000_000_000;
  vi.spyOn(Date, "now").mockImplementation(() => clockMs);
  window.SpeechRecognition = FakeRecognition as unknown as SpeechRecognitionConstructor;
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  delete window.SpeechRecognition;
});

describe("Composer — nút mic", () => {
  it("trình duyệt không hỗ trợ thì không render nút mic, ô nhập vẫn gửi được", async () => {
    delete window.SpeechRecognition;
    const onSend = vi.fn();
    render(<Composer disabled={false} onSend={onSend} />);

    expect(screen.queryByRole("button", { name: "Nói" })).not.toBeInTheDocument();
    await userEvent.type(textarea(), "Cách mạng Tháng Tám");
    await userEvent.click(sendButton());
    expect(onSend).toHaveBeenCalledWith("Cách mạng Tháng Tám");
  });

  it("bấm mic thì bắt đầu nghe và khoá ô nhập lẫn nút Gửi", async () => {
    render(<Composer disabled={false} onSend={vi.fn()} />);
    await userEvent.type(textarea(), "abc");

    await userEvent.click(micButton());

    expect(FakeRecognition.instances).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Dừng nói" })).toBeInTheDocument();
    expect(textarea()).toHaveAttribute("readonly");
    expect(sendButton()).toBeDisabled();
  });

  it("cấu hình engine cho tiếng Việt, có interim, nghe liên tục", async () => {
    render(<Composer disabled={false} onSend={vi.fn()} />);
    await userEvent.click(micButton());

    expect(lastRecognition().lang).toBe("vi-VN");
    expect(lastRecognition().interimResults).toBe(true);
    expect(lastRecognition().continuous).toBe(true);
  });

  it("result phát lại nhiều lần không làm nhân đôi chữ", async () => {
    render(<Composer disabled={false} onSend={vi.fn()} />);
    await userEvent.click(micButton());

    lastRecognition().emitResults("Cách mạng");
    lastRecognition().emitResults("Cách mạng Tháng Tám");
    lastRecognition().emitResults("Cách mạng Tháng Tám", " năm 1945");

    expect(textarea()).toHaveValue("Cách mạng Tháng Tám năm 1945");
  });

  it("chữ đọc ra nối SAU phần đã gõ tay", async () => {
    render(<Composer disabled={false} onSend={vi.fn()} />);
    await userEvent.type(textarea(), "Cho tôi hỏi");

    await userEvent.click(micButton());
    lastRecognition().emitResults("ý nghĩa Cách mạng Tháng Tám");

    expect(textarea()).toHaveValue("Cho tôi hỏi ý nghĩa Cách mạng Tháng Tám");
  });

  it("Chrome tự đóng phiên giữa chừng thì nghe tiếp, chữ phiên trước không mất", async () => {
    render(<Composer disabled={false} onSend={vi.fn()} />);
    await userEvent.click(micButton());
    lastRecognition().emitResults("Cách mạng Tháng Tám");

    clockMs += 5_000;
    lastRecognition().emitEnd();

    expect(FakeRecognition.instances).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Dừng nói" })).toBeInTheDocument();

    // Phiên mới bắt đầu với `results` rỗng — chữ cũ phải nằm ngoài nó mới không bị đè.
    lastRecognition().emitResults("thành công năm 1945");
    expect(textarea()).toHaveValue("Cách mạng Tháng Tám thành công năm 1945");
  });

  it("phiên đóng lại tức thì thì dừng hẳn, không quay vòng mở phiên", async () => {
    render(<Composer disabled={false} onSend={vi.fn()} />);
    await userEvent.click(micButton());

    lastRecognition().emitEnd();

    expect(FakeRecognition.instances).toHaveLength(1);
    expect(screen.getByRole("alert")).toHaveTextContent("Không nghe được từ micro");
    expect(screen.getByRole("button", { name: "Nói" })).toBeInTheDocument();
  });

  it("bấm dừng thì mở khoá ngay, và chữ về SAU đó vẫn vào ô nhập", async () => {
    render(<Composer disabled={false} onSend={vi.fn()} />);
    await userEvent.click(micButton());
    lastRecognition().emitResults("Cách mạng Tháng Tám");

    await userEvent.click(micButton());

    expect(lastRecognition().stopCount).toBe(1);
    expect(screen.getByRole("button", { name: "Nói" })).toBeInTheDocument();
    expect(textarea()).not.toHaveAttribute("readonly");

    // engine thật còn trả nốt một result sau `stop()` — không được để rơi mất
    lastRecognition().emitResults("Cách mạng Tháng Tám năm 1945");
    expect(textarea()).toHaveValue("Cách mạng Tháng Tám năm 1945");
  });

  it("bị chặn quyền mic thì báo lỗi và KHÔNG mở lại phiên", async () => {
    render(<Composer disabled={false} onSend={vi.fn()} />);
    await userEvent.click(micButton());

    clockMs += 5_000;
    lastRecognition().emitError("not-allowed");
    lastRecognition().emitEnd();

    expect(FakeRecognition.instances).toHaveLength(1);
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Bạn cần cho phép dùng micro trong trình duyệt.",
    );
    expect(screen.getByRole("button", { name: "Nói" })).toBeInTheDocument();
  });

  it("im lặng lâu (no-speech) không báo lỗi, vẫn nghe tiếp", async () => {
    render(<Composer disabled={false} onSend={vi.fn()} />);
    await userEvent.click(micButton());

    clockMs += 5_000;
    lastRecognition().emitError("no-speech");
    lastRecognition().emitEnd();

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(FakeRecognition.instances).toHaveLength(2);
  });

  it("mic tự tắt sau 60 giây để không mở quên cả buổi", () => {
    vi.useFakeTimers();
    render(<Composer disabled={false} onSend={vi.fn()} />);
    fireEvent.click(micButton());

    act(() => {
      vi.advanceTimersByTime(60_000);
    });

    expect(lastRecognition().stopCount).toBe(1);
    expect(screen.getByRole("button", { name: "Nói" })).toBeInTheDocument();
    vi.useRealTimers();
  });

  it("nói xong sửa tay rồi gửi được như thường", async () => {
    const onSend = vi.fn();
    render(<Composer disabled={false} onSend={onSend} />);
    await userEvent.click(micButton());
    lastRecognition().emitResults("Cách mạng Tháng Tám");
    await userEvent.click(micButton());

    await userEvent.type(textarea(), " năm 1945");
    await userEvent.click(sendButton());

    expect(onSend).toHaveBeenCalledWith("Cách mạng Tháng Tám năm 1945");
  });

  it("bắt đầu stream câu trả lời khi mic đang mở thì mic tự tắt", async () => {
    // Đường vào: bấm câu hỏi mẫu ở empty-state trong lúc đang nói.
    const { rerender } = render(<Composer disabled={false} onSend={vi.fn()} />);
    await userEvent.click(micButton());

    rerender(<Composer disabled onSend={vi.fn()} />);

    expect(lastRecognition().stopCount).toBe(1);
    expect(screen.getByRole("button", { name: "Nói" })).toBeInTheDocument();
  });

  it("rời trang khi đang nghe thì mic được tắt hẳn", async () => {
    const { unmount } = render(<Composer disabled={false} onSend={vi.fn()} />);
    await userEvent.click(micButton());

    unmount();

    expect(lastRecognition().abortCount).toBe(1);
  });
});
