import type { ComponentType, ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import * as Tooltip from "@radix-ui/react-tooltip";
import {
  FileText,
  Landmark,
  Library,
  LogOut,
  MessageSquare,
  PanelLeft,
  SlidersHorizontal,
} from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { useUiStore } from "@/store/uiStore";

interface NavItem {
  to: string;
  label: string;
  icon: ComponentType<{ size?: number | string; className?: string }>;
  end: boolean;
  adminOnly: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Hỏi đáp", icon: MessageSquare, end: true, adminOnly: false },
  { to: "/admin/documents", label: "Tài liệu", icon: FileText, end: false, adminOnly: true },
  { to: "/admin/kb", label: "Kho tri thức", icon: Library, end: false, adminOnly: true },
  { to: "/admin/advanced", label: "Nâng cao", icon: SlidersHorizontal, end: false, adminOnly: true },
];

const iconOnlyButtonClass =
  "flex h-10 w-10 items-center justify-center rounded-md transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/30";

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
          className="z-50 rounded-md bg-ink px-2.5 py-1.5 text-xs font-medium text-white shadow-md"
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
        className={`text-sm ${
          open
            ? "flex h-10 w-full items-center gap-3 rounded-md px-3 transition-colors"
            : iconOnlyButtonClass
        } ${
          active
            ? "bg-brand font-medium text-brand-fg shadow-sm"
            : "text-ink-soft hover:bg-paper hover:text-brand"
        }`}
      >
        <Icon size={open ? 18 : 20} className="shrink-0" />
        {open && <span className="truncate">{item.label}</span>}
      </Link>
    </WithTooltip>
  );
}

/** Sidebar điều hướng dọc dùng chung cả app (user + admin), đóng/mở persist qua uiStore.
 * Mở: icon + tên; đóng: chỉ icon, hover có tooltip. Đăng xuất + email user nằm ở đáy. */
export function AppSidebar() {
  const open = useUiStore((s) => s.sidebarOpen);
  const toggleSidebar = useUiStore((s) => s.toggleSidebar);
  const user = useAuthStore((s) => s.user);
  const isAdmin = useAuthStore((s) => s.user?.role === "admin");
  const clear = useAuthStore((s) => s.clear);
  const location = useLocation();
  const navigate = useNavigate();

  const items = NAV_ITEMS.filter((i) => !i.adminOnly || isAdmin);

  function onLogout() {
    clear();
    navigate("/login", { replace: true });
  }

  return (
    <Tooltip.Provider delayDuration={200}>
      <aside
        className={`flex shrink-0 flex-col border-r border-paper-border bg-paper-card transition-[width] duration-200 ${
          open ? "w-60" : "w-[4.5rem]"
        }`}
      >
        <div
          className={`flex border-b border-paper-border/70 ${
            open ? "h-16 items-center justify-between px-4" : "h-24 flex-col items-center justify-center gap-2"
          }`}
        >
          {open ? (
            <span className="font-serif text-lg font-bold text-brand">Sử Việt</span>
          ) : (
            <span className="flex h-9 w-9 items-center justify-center rounded-md border border-brand/20 bg-brand/10 text-brand">
              <Landmark size={18} />
            </span>
          )}
          <WithTooltip open={open} label={open ? "Thu gọn menu" : "Mở rộng menu"}>
            <button
              onClick={toggleSidebar}
              aria-label={open ? "Thu gọn menu" : "Mở rộng menu"}
              className={`${iconOnlyButtonClass} text-ink-soft hover:bg-paper hover:text-brand ${
                open ? "h-9 w-9" : ""
              }`}
            >
              <PanelLeft size={20} className={open ? undefined : "rotate-180"} />
            </button>
          </WithTooltip>
        </div>

        <nav
          className={
            open ? "flex-1 space-y-1 px-2 py-3" : "flex flex-1 flex-col items-center gap-2 py-3"
          }
        >
          {items.map((item) => (
            <SidebarLink
              key={item.to}
              item={item}
              open={open}
              active={isItemActive(location.pathname, item)}
            />
          ))}
        </nav>

        <div
          className={
            open
              ? "space-y-1 border-t border-paper-border p-2"
              : "flex flex-col items-center gap-2 border-t border-paper-border p-2"
          }
        >
          {open && <p className="truncate px-3 pt-1 text-xs text-ink-soft">{user?.email}</p>}
          <WithTooltip open={open} label="Đăng xuất">
            <button
              onClick={onLogout}
              aria-label={open ? undefined : "Đăng xuất"}
              className={`text-sm text-ink-soft hover:bg-paper hover:text-brand ${
                open
                  ? "flex h-10 w-full items-center gap-3 rounded-md px-3 transition-colors"
                  : iconOnlyButtonClass
              }`}
            >
              <LogOut size={open ? 18 : 20} className="shrink-0" />
              {open && <span>Đăng xuất</span>}
            </button>
          </WithTooltip>
        </div>
      </aside>
    </Tooltip.Provider>
  );
}
