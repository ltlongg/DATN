import type { ReactNode } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";

const WIDTH = {
  md: "max-w-md", // form/confirm ở khu admin
  lg: "max-w-2xl", // khối văn bản dài (xem nguồn) — hẹp hơn thì chữ vỡ dòng liên tục
} as const;

/** Modal accessible (Radix Dialog). Dùng cho form/confirm ở khu admin + xem nguồn ở chat. */
export function Modal({
  open,
  onOpenChange,
  title,
  size = "md",
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  size?: keyof typeof WIDTH;
  children: ReactNode;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 animate-fade-in bg-night/40 backdrop-blur-[2px]" />
        <Dialog.Content
          aria-describedby={undefined}
          className={`fixed left-1/2 top-1/2 z-50 w-[calc(100%-2rem)] ${WIDTH[size]} -translate-x-1/2 -translate-y-1/2 animate-pop-in rounded-2xl border border-paper-border bg-paper-card p-6 shadow-pop focus:outline-none`}
        >
          <Dialog.Title className="pr-8 font-serif text-lg font-semibold text-ink">{title}</Dialog.Title>
          <div className="mt-4">{children}</div>
          {/* Nút đóng đứng SAU nội dung trong DOM (hiển thị ở góc nhờ absolute): Radix focus phần
              tử bấm được đầu tiên khi mở, nên ô nhập đầu của form được focus thay vì nút X. */}
          <Dialog.Close
            className="btn btn-ghost btn-icon absolute right-4 top-4 h-8 w-8"
            aria-label="Đóng"
          >
            <X size={18} />
          </Dialog.Close>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
