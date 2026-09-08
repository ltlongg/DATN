import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { getFigure } from "@/features/figures/registry";
import type { Figure } from "@/features/figures/types";
import "@/features/figures/figure-fonts.css";
import "@/features/figures/figure-page.css";

/**
 * Trang một danh nhân. CỐ Ý nằm ngoài `AppShell` (xem app/routes.tsx): trang chuyên đề nền
 * tối chiếm trọn màn hình, không có sidebar, chỉ còn nút quay lại.
 *
 * Ngoài AppShell nghĩa là thoát `h-screen overflow-hidden`, nên trang cuộn CỬA SỔ như một
 * trang web thường — nhờ vậy hai hiệu ứng bê từ bản mockup (thanh trên đặc dần, khối chữ
 * hiện dần) dùng thẳng `window`/`IntersectionObserver` mặc định, không phải trỏ vào khung
 * cuộn riêng như các trang trong shell.
 */
export default function FigurePage() {
  const { slug = "" } = useParams();
  // undefined = đang tải, null = không có danh nhân này.
  const [figure, setFigure] = useState<Figure | null | undefined>(undefined);
  const [scrolled, setScrolled] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let alive = true;
    setFigure(undefined);
    getFigure(slug).then((f) => {
      if (alive) setFigure(f);
    });
    return () => {
      alive = false;
    };
  }, [slug]);

  // Nền tối + cuộn mượt + bỏ height:100% của #root — ba thứ thuộc về <html>, không gói
  // trong .figure-page được. Gỡ khi rời trang để không dính sang phần còn lại của app.
  useEffect(() => {
    document.documentElement.classList.add("figure-page-open");
    return () => document.documentElement.classList.remove("figure-page-open");
  }, []);

  useEffect(() => {
    function onScroll() {
      setScrolled(window.scrollY > window.innerHeight * 0.75);
    }
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Chạy lại khi `figure` đổi: trước đó các khối .rv chưa được render nên không có gì để quan sát.
  useEffect(() => {
    const root = rootRef.current;
    if (!root || !figure) return;
    const observer = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            e.target.classList.add("in");
            observer.unobserve(e.target);
          }
        }
      },
      { rootMargin: "0px 0px -12% 0px", threshold: 0.08 },
    );
    root.querySelectorAll(".rv").forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, [figure]);

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [slug]);

  if (figure === undefined) return <div className="figure-page" />;

  if (figure === null) {
    return (
      <div className="figure-page">
        <div className="wrap" style={{ paddingTop: 140 }}>
          <p style={{ color: "#c9c0b2" }}>Chưa có bài viết về danh nhân này.</p>
          <Link to="/" style={{ color: "#d9b166" }}>
            ← Về trang hỏi đáp
          </Link>
        </div>
      </div>
    );
  }

  const { Article } = figure;

  return (
    <div className="figure-page" ref={rootRef}>
      <div className={`topbar${scrolled ? " on" : ""}`}>
        <Link to="/" className="back">
          <ArrowLeft size={15} />
          Quay lại
        </Link>
        <span className="nm">{figure.name}</span>
        <span className="yr">{figure.lifespan}</span>
        <nav>
          {figure.sections.map((s) => (
            <a key={s.id} href={`#${s.id}`}>
              {s.label}
            </a>
          ))}
        </nav>
      </div>
      <Article />
    </div>
  );
}
