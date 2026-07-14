import type { ReactNode } from "react";
import * as Dialog from "@radix-ui/react-dialog";

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
        <Dialog.Overlay className="fixed inset-0 bg-black/30" />
        <Dialog.Content
          className={`fixed left-1/2 top-1/2 w-full ${WIDTH[size]} -translate-x-1/2 -translate-y-1/2 rounded-xl border border-paper-border bg-paper-card p-6 shadow-lg focus:outline-none`}
        >
          <Dialog.Title className="text-lg font-semibold text-ink">{title}</Dialog.Title>
          <div className="mt-4">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
