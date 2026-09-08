import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { getCampaign } from "@/features/campaigns/registry";
import type { Campaign } from "@/features/campaigns/types";
import "@/features/campaigns/campaign-page.css";

/**
 * Trang một chiến dịch. CỐ Ý nằm ngoài `AppShell` (xem app/routes.tsx), cùng lý do như
 * `FigurePage`: bản dựng cần cả chiều ngang cho hai khung hình đặt cạnh nhau, có sidebar
 * thì phối cảnh bị bóp lại.
 *
 * Ngoài AppShell nghĩa là thoát `h-screen overflow-hidden`, nên trang cuộn CỬA SỔ bình
 * thường khi màn hình thấp hơn chiều cao của bản dựng.
 */
export default function CampaignPage() {
  const { slug = "" } = useParams();
  // undefined = đang tải, null = không có chiến dịch này.
  const [campaign, setCampaign] = useState<Campaign | null | undefined>(undefined);

  useEffect(() => {
    let alive = true;
    setCampaign(undefined);
    getCampaign(slug).then((c) => {
      if (alive) setCampaign(c);
    });
    return () => {
      alive = false;
    };
  }, [slug]);

  // Bỏ height:100% của #root và đổi nền cửa sổ — hai thứ thuộc về <html>, không gói trong
  // .campaign-page được. Gỡ khi rời trang để không dính sang phần còn lại của app.
  useEffect(() => {
    document.documentElement.classList.add("campaign-page-open");
    return () => document.documentElement.classList.remove("campaign-page-open");
  }, []);

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [slug]);

  if (campaign === undefined) return <div className="campaign-page" />;

  if (campaign === null) {
    return (
      <div className="campaign-page">
        <div className="back-row">
          <Link to="/" className="back">
            <ArrowLeft size={14} />
            Quay lại
          </Link>
        </div>
        <main>
          <p>Chưa có bản dựng cho chiến dịch này.</p>
        </main>
      </div>
    );
  }

  const { Board } = campaign;

  return (
    <div className="campaign-page" aria-label={`Chiến dịch ${campaign.name}`}>
      <div className="back-row">
        <Link to="/" className="back">
          <ArrowLeft size={14} />
          Quay lại
        </Link>
        <span className="crumb">{campaign.period}</span>
      </div>
      <Board />
    </div>
  );
}
