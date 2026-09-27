import { Fragment, type ComponentType, type ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import * as Tooltip from "@radix-ui/react-tooltip";
import {
  Activity,
  CalendarClock,
  Coins,
  FileStack,
  FileText,
  LogOut,
  MessagesSquare,
  MessageSquare,
  Milestone,
  PanelLeftClose,
  PanelLeftOpen,
  Settings,
  Share2,
  SlidersHorizontal,
  Users,
  Wand2,
} from "lucide-react";
import { BrandMark } from "@/components/BrandMark";
import { useAuthStore } from "@/store/authStore";
import { useUiStore } from "@/store/uiStore";

interface NavItem {
  to: string;
  label: string;
  icon: ComponentType<{ size?: number | string; className?: string }>;
  end: boolean;
  adminOnly: boolean;
  /** Nhãn nhóm (viết hoa) — `undefined` = mục không nhóm ở đầu. Item cùng group đứng liền kề. */
  group?: string;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Hỏi đáp", icon: MessageSquare, end: true, adminOnly: false },
  { to: "/timeline", label: "Dòng lịch sử", icon: Milestone, end: false, adminOnly: false },
  { to: "/admin/documents", label: "Tài liệu", icon: FileText, end: false, adminOnly: true, group: "NỘI DUNG" },
  { to: "/admin/kb/chunks", label: "Đoạn tài liệu", icon: FileStack, end: false, adminOnly: true, group: "KHO TRI THỨC" },
  { to: "/admin/kb/graph", label: "Đồ thị tri thức", icon: Share2, end: false, adminOnly: true, group: "KHO TRI THỨC" },
  { to: "/admin/kb/timeline", label: "Dòng thời gian", icon: CalendarClock, end: false, adminOnly: true, group: "KHO TRI THỨC" },
  { to: "/admin/logs", label: "Hội thoại", icon: MessagesSquare, end: false, adminOnly: true, group: "QUẢN TRỊ" },
  { to: "/admin/users", label: "Người dùng & quota", icon: Users, end: false, adminOnly: true, group: "QUẢN TRỊ" },
  { to: "/admin/cost", label: "Chi phí", icon: Coins, end: false, adminOnly: true, group: "QUẢN TRỊ" },
  { to: "/admin/activity", label: "Hoạt động hệ thống", icon: Activity, end: false, adminOnly: true, group: "QUẢN TRỊ" },
  { to: "/admin/prompts", label: "Quản lý Prompt", icon: Wand2, end: false, adminOnly: true, group: "QUẢN TRỊ" },
  { to: "/admin/config", label: "Cấu hình hệ thống", icon: SlidersHorizontal, end: false, adminOnly: true, group: "QUẢN TRỊ" },
];

/** Ở đáy sidebar (cạnh thẻ người dùng), không nằm trong nav chính. */
const SETTINGS_ITEM: NavItem = {
  to: "/settings",
  label: "Cài đặt",
  icon: Settings,
  end: false,
  adminOnly: false,
};

/** Dáng chung cho mục nav + nút đáy sidebar: mở = hàng icon + chữ; đóng = ô vuông chỉ icon. */
function rowClass(open: boolean) {
  return `flex items-center rounded-lg text-sm transition-colors focus-visible:ring-offset-night ${
    open ? "h-10 w-full gap-3 px-3" : "h-10 w-10 justify-center"
  }`;
}

const IDLE = "text-night-text hover:bg-night-raised hover:text-white";

/** Khi sidebar đóng chỉ còn icon -> bọc tooltip Radix hiện label bên phải. Mở thì render trần. */
function WithTooltip({ open, label, children }: { open: boolean; label: string; children: ReactNode }) {
  if (open) return <>{children}</>;
  return (
    <Tooltip.Root>
      <Tooltip.Trigger asChild>{children}</Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content
          side="right"
          sideOffset={10}
          className="z-50 rounded-md bg-ink px-2.5 py-1.5 text-xs font-medium text-white shadow-pop"
        >
          {label}
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  );
}

function isItemActive(pathname: string, item: NavItem) {
  if (item.end) return pathname === item.to;
  return pathname === item.to || pathname.startsWith(`${item.to}/`);
}

function SidebarLink({ item, open, active }: { item: NavItem; open: boolean; active: boolean }) {
  const Icon = item.icon;
  return (
    <WithTooltip open={open} label={item.label}>
      <Link
        to={item.to}
        aria-current={active ? "page" : undefined}
        aria-label={open ? undefined : item.label}
        className={`${rowClass(open)} ${
          active ? "bg-brand font-medium text-white shadow-sm" : IDLE
        }`}
      >
        <Icon size={18} className="shrink-0" />
        {open && <span className="truncate">{item.label}</span>}
      </Link>
    </WithTooltip>
  );
}

function SidebarButton({
  open,
  label,
  icon: Icon,
  onClick,
}: {
  open: boolean;
  label: string;
  icon: NavItem["icon"];
  onClick: () => void;
}) {
  return (
    <WithTooltip open={open} label={label}>
      <button
        onClick={onClick}
        aria-label={open ? undefined : label}
        className={`${rowClass(open)} ${IDLE}`}
      >
        <Icon size={18} className="shrink-0" />
        {open && <span>{label}</span>}
      </button>
    </WithTooltip>
  );
}

/** Sidebar điều hướng dọc dùng chung cả app (user + admin), đóng/mở persist qua uiStore.
 * Mở: icon + tên; đóng: chỉ icon, hover có tooltip. Thẻ người dùng + cài đặt + đăng xuất
 * nằm ở đáy. */
export function AppSidebar() {
  const open = useUiStore((s) => s.sidebarOpen);
  const toggleSidebar = useUiStore((s) => s.toggleSidebar);
  const user = useAuthStore((s) => s.user);
  const isAdmin = useAuthStore((s) => s.user?.role === "admin");
  const clear = useAuthStore((s) => s.clear);
  const location = useLocation();
  const navigate = useNavigate();

  const items = NAV_ITEMS.filter((i) => !i.adminOnly || isAdmin);
  const toggleLabel = open ? "Thu gọn menu" : "Mở rộng menu";
  const initial = user?.name.trim().charAt(0).toUpperCase() || "?";

  function onLogout() {
    clear();
    navigate("/login", { replace: true });
  }

  return (
    <Tooltip.Provider delayDuration={200}>
      <aside
        className={`flex shrink-0 flex-col bg-night transition-[width] duration-200 ${
          open ? "w-64" : "w-[4.5rem]"
        }`}
      >
        <div
          className={`flex shrink-0 ${
            open ? "h-16 items-center gap-3 px-4" : "flex-col items-center gap-3 py-4"
          }`}
        >
          <BrandMark />
          {open && (
            <div className="min-w-0 flex-1 leading-tight">
              <p className="font-serif text-base font-bold text-white">Sử Việt</p>
              <p className="text-[11px] text-night-muted">Trợ lý lịch sử Việt Nam</p>
            </div>
          )}
          <WithTooltip open={open} label={toggleLabel}>
            <button
              onClick={toggleSidebar}
              aria-label={toggleLabel}
              className="flex h-8 w-8 items-center justify-center rounded-lg text-night-muted transition-colors hover:bg-night-raised hover:text-white focus-visible:ring-offset-night"
            >
              {open ? <PanelLeftClose size={18} /> : <PanelLeftOpen size={18} />}
            </button>
          </WithTooltip>
        </div>

        <nav
          className={`scrollbar-night flex-1 overflow-y-auto py-2 ${
            open ? "space-y-0.5 px-3" : "flex flex-col items-center gap-1"
          }`}
        >
          {items.map((item, i) => {
            const groupChanged = item.group !== items[i - 1]?.group;
            return (
              <Fragment key={item.to}>
                {groupChanged &&
                  (open
                    ? item.group && (
                        <p className="px-3 pb-1.5 pt-5 text-[11px] font-semibold uppercase tracking-wider text-night-muted">
                          {item.group}
                        </p>
                      )
                    : i > 0 && <div className="my-2 h-px w-6 bg-night-border" />)}
                <SidebarLink item={item} open={open} active={isItemActive(location.pathname, item)} />
              </Fragment>
            );
          })}
        </nav>

        <div
          className={`shrink-0 border-t border-night-border p-3 ${
            open ? "space-y-0.5" : "flex flex-col items-center gap-1"
          }`}
        >
          {open && user && (
            <div className="mb-2 flex items-center gap-3 rounded-lg bg-night-raised px-3 py-2.5">
              <span
                aria-hidden
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand text-xs font-semibold text-white"
              >
                {initial}
              </span>
              <div className="min-w-0 leading-tight">
                <p className="truncate text-sm font-medium text-white">{user.name}</p>
                <p className="truncate text-xs text-night-muted">{user.email}</p>
              </div>
            </div>
          )}
          <SidebarLink
            item={SETTINGS_ITEM}
            open={open}
            active={isItemActive(location.pathname, SETTINGS_ITEM)}
          />
          <SidebarButton open={open} label="Đăng xuất" icon={LogOut} onClick={onLogout} />
        </div>
      </aside>
    </Tooltip.Provider>
  );
}
