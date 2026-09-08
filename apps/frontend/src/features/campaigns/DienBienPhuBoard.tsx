import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { chapters } from "./dien-bien-phu-1954.data";
import { definitions, frame } from "./dien-bien-phu-1954.draw";

/**
 * Bản dựng chiến dịch Điện Biên Phủ: 9 cảnh × 3 bước, phối cảnh bên trái và lược đồ bên
 * phải luôn cùng một bước.
 *
 * Chuyển từ bản thử `docs/design/mockups/chien-dich-dien-bien-phu-1954.js`. Bản thử là một
 * IIFE tự ghi DOM qua `getElementById` + `innerHTML`; ở đây chỉ có `{ci, bi}` là state, còn
 * hình vẫn do `frame()` sinh ra dưới dạng chuỗi (xem docstring của tệp draw).
 *
 * `elapsed` CỐ Ý nằm trong ref chứ không phải state: nó đổi 60 lần/giây mà chỉ dùng để kéo
 * thanh tiến độ, để trong state thì cả cây phải render lại mỗi khung hình. Vòng lặp ghi
 * thẳng chiều rộng của thanh qua `progressRef`.
 *
 * `posRef` là bản sao của `{ci, bi}` cho vòng `requestAnimationFrame` đọc: hàm `tick` được
 * tạo một lần cho mỗi lần bật chạy nên không thấy được state mới nếu đọc trực tiếp.
 */

const SPEEDS = [
  { value: 4000, label: "Nhanh · ~2 phút" },
  { value: 6000, label: "Vừa · ~3 phút" },
  { value: 9000, label: "Chậm · ~4 phút" },
];

const LAST = chapters.length - 1;

export function DienBienPhuBoard() {
  const [pos, setPos] = useState({ ci: 0, bi: 0 });
  const [running, setRunning] = useState(false);
  // Đang dừng GIỮA CHỪNG (khác với chưa chạy lần nào) -> đóng băng animation của cảnh.
  const [halted, setHalted] = useState(false);
  const [speed, setSpeed] = useState(SPEEDS[0].value);
  const [reduced, setReduced] = useState(
    () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false,
  );

  const posRef = useRef(pos);
  const elapsedRef = useRef(0);
  // Chỉ diễn lại cảnh hiện tại rồi dừng, không chạy tiếp sang cảnh sau.
  const chapterOnlyRef = useRef(false);
  const progressRef = useRef<HTMLDivElement>(null);

  const paint = useCallback(() => {
    const bar = progressRef.current;
    if (bar) bar.style.width = `${(elapsedRef.current / speed) * 100}%`;
  }, [speed]);

  // Đổi nhịp kể thì thanh tiến độ phải vẽ lại theo mốc mới, kể cả lúc đang dừng.
  useEffect(() => {
    paint();
  }, [paint]);

  const move = useCallback((next: { ci: number; bi: number }) => {
    posRef.current = next;
    setPos(next);
  }, []);

  const select = useCallback(
    (c: number, b: number) => {
      setRunning(false);
      setHalted(false);
      elapsedRef.current = 0;
      chapterOnlyRef.current = false;
      move({ ci: Math.max(0, Math.min(LAST, c)), bi: b });
      paint();
    },
    [move, paint],
  );

  const pause = useCallback(() => {
    setRunning(false);
    setHalted(elapsedRef.current > 0);
  }, []);

  const play = useCallback(() => {
    chapterOnlyRef.current = false;
    const { ci, bi } = posRef.current;
    // Đang đứng ở cuối chiến dịch thì bấm phát là quay lại cảnh đầu.
    if (ci === LAST && bi === 2 && elapsedRef.current >= speed) {
      elapsedRef.current = 0;
      move({ ci: 0, bi: 0 });
    }
    setHalted(false);
    setRunning(true);
  }, [move, speed]);

  const replay = useCallback(() => {
    elapsedRef.current = 0;
    chapterOnlyRef.current = true;
    move({ ci: posRef.current.ci, bi: 0 });
    setHalted(false);
    setRunning(true);
  }, [move]);

  useEffect(() => {
    if (!running) return;
    let raf = 0;
    let last = 0;
    const tick = (now: number) => {
      if (last) elapsedRef.current += now - last;
      last = now;
      if (elapsedRef.current >= speed) {
        elapsedRef.current = 0;
        const { ci, bi } = posRef.current;
        if (bi < 2) {
          move({ ci, bi: bi + 1 });
        } else if (ci === LAST || chapterOnlyRef.current) {
          elapsedRef.current = speed;
          paint();
          setRunning(false);
          setHalted(true);
          return;
        } else {
          move({ ci: ci + 1, bi: 0 });
        }
      }
      paint();
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [running, speed, move, paint]);

  // Chuyển sang tab khác thì dừng: chạy tiếp trong nền chỉ tốn khung hình và làm người xem
  // quay lại thấy mình lỡ mất mấy cảnh.
  useEffect(() => {
    function onVisibility() {
      if (document.hidden) pause();
    }
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, [pause]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const el = e.target as HTMLElement;
      if (["INPUT", "SELECT", "TEXTAREA", "BUTTON"].includes(el.tagName) || el.isContentEditable) return;
      if (e.key === "ArrowRight") {
        e.preventDefault();
        select(posRef.current.ci + 1, 0);
      }
      if (e.key === "ArrowLeft") {
        e.preventDefault();
        select(posRef.current.ci - 1, 0);
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [select]);

  // Địa điểm nằm trong markup do `frame()` sinh ra nên không gắn được onClick lên từng
  // cái: bắt sự kiện ở thẻ cha rồi lần ngược lên `[data-chapter]`.
  const jumpFromMarkup = useCallback(
    (target: EventTarget | null) => {
      const hit = (target as Element | null)?.closest?.("[data-chapter]");
      if (!hit) return false;
      select(Number(hit.getAttribute("data-chapter")), 0);
      return true;
    },
    [select],
  );

  const { ci, bi } = pos;
  const chapter = chapters[ci];
  const step = chapter.beats[bi];
  const view = useMemo(() => frame(ci, bi), [ci, bi]);

  const panels = {
    onClick: (e: React.MouseEvent) => {
      jumpFromMarkup(e.target);
    },
    onKeyDown: (e: React.KeyboardEvent) => {
      if (e.key !== "Enter" && e.key !== " ") return;
      if (jumpFromMarkup(e.target)) e.preventDefault();
    },
  };

  return (
    <>
      <header>
        <div>
          <div className="eyebrow">Theo dấu chiến dịch · 1954</div>
          <h1>Điện Biên Phủ</h1>
          <p className="intro">Từ trận mở màn đến khu chỉ huy Mường Thanh.</p>
        </div>
        <div className="edition">9 CẢNH TƯƠNG TÁC</div>
      </header>

      <main>
        <div className={`theater${!running && halted ? " paused" : ""}${reduced ? " reduced" : ""}`}>
          <section className="panel scene" aria-label="Phối cảnh diễn biến">
            <div className="panel-tag">
              {view.cut ? "A1 / TIẾP CẬN DƯỚI LÒNG ĐẤT" : "PHỐI CẢNH TRẬN ĐỊA"}
            </div>
            <div className="scene-top">
              <strong>{chapter.date} · 1954</strong>
              <span>{step.time}</span>
            </div>
            <svg
              viewBox="0 0 960 640"
              role="group"
              aria-label="Cảnh chiến dịch Điện Biên Phủ"
              {...panels}
            >
              <g dangerouslySetInnerHTML={{ __html: definitions }} />
              {/* Thẻ <g> này CỐ Ý giữ nguyên qua các lần render (chỉ đổi ruột và transform)
                  để CSS transition của camera có mốc cũ mà nội suy. */}
              <g
                className="world"
                style={{ transform: view.transform, visibility: view.cut ? "hidden" : "visible" }}
                dangerouslySetInnerHTML={{ __html: view.world }}
              />
              <g dangerouslySetInnerHTML={{ __html: view.detail }} />
            </svg>
            <div className="scene-bottom">
              <span className="scene-note">Phối cảnh minh họa · Không theo tỷ lệ</span>
              <div className="action-label">
                <span>
                  {bi + 1}/3 · {step.label}
                </span>
                <div>{step.action}</div>
              </div>
            </div>
          </section>

          <section className="panel map" aria-label="Bản đồ chiến dịch">
            <div className="panel-tag">TOÀN CẢNH · BẮC Ở PHÍA TRÊN</div>
            <svg
              viewBox="140 0 620 760"
              role="group"
              aria-label="Lược đồ Điện Biên Phủ đồng bộ theo diễn biến"
              dangerouslySetInnerHTML={{ __html: view.map }}
              {...panels}
            />
            <div className="map-legend">
              <span>
                <i />
                Cứ điểm Pháp
              </span>
              <span>
                <i className="taken" />
                Đã kiểm soát
              </span>
              <span>
                <i className="focus" />
                Đang xem
              </span>
            </div>
          </section>
        </div>

        <nav className="chapter-strip" aria-label="Chọn cảnh chiến dịch">
          {chapters.map((c, i) => (
            <button
              key={c.id}
              className={`chapter${i === ci ? " active" : i < ci ? " done" : ""}`}
              aria-current={i === ci ? "step" : undefined}
              onClick={() => select(i, 0)}
            >
              <small>{c.date}</small>
              <strong>{c.name}</strong>
            </button>
          ))}
        </nav>

        <section className="reading" aria-live="polite" aria-atomic="true">
          <div>
            <div className="eyebrow">{chapter.phase}</div>
            <h2>{chapter.title}</h2>
          </div>
          <p>{step.text}</p>
          <div className="result">
            <strong>ĐIỀU THAY ĐỔI</strong>
            <span>{chapter.result}</span>
          </div>
        </section>

        <nav className="microsteps" aria-label="Các bước trong cảnh">
          <span>TRONG CẢNH NÀY</span>
          {chapter.beats.map((b, i) => (
            <button
              key={b.label}
              className={`beat${i === bi ? " active" : ""}`}
              aria-pressed={i === bi}
              onClick={() => select(ci, i)}
            >
              <b>0{i + 1}</b>
              {b.label}
            </button>
          ))}
        </nav>

        <div className="transport">
          <button onClick={() => select(ci - 1, 0)} disabled={ci === 0} aria-label="Cảnh trước">
            ←
          </button>
          <button
            className="play"
            aria-pressed={running}
            onClick={() => (running ? pause() : play())}
          >
            {running ? "Ⅱ Tạm dừng" : "▶ Trình chiếu"}
          </button>
          <button onClick={() => select(ci + 1, 0)} disabled={ci === LAST} aria-label="Cảnh tiếp theo">
            →
          </button>
          <button onClick={replay}>↻ Diễn lại cảnh</button>
          <span className="spacer" />
          <label htmlFor="dbp-speed">Nhịp kể</label>
          <select
            id="dbp-speed"
            value={speed}
            onChange={(e) => {
              elapsedRef.current = 0;
              setSpeed(Number(e.target.value));
            }}
          >
            {SPEEDS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
          <label>
            <input
              type="checkbox"
              checked={reduced}
              onChange={(e) => setReduced(e.target.checked)}
            />{" "}
            Giảm chuyển động
          </label>
        </div>
        <div className="progress">
          <div ref={progressRef} />
        </div>

        <div className="footer">
          <span>
            Cảnh {ci + 1}/{chapters.length} · Bước {bi + 1}/3 · Địa hình và hướng hoạt động được
            khái quát.
          </span>
          <span>← → đổi cảnh · Bấm địa điểm để xem · Mũi tên chỉ hướng hoạt động khái quát</span>
        </div>
      </main>
    </>
  );
}
