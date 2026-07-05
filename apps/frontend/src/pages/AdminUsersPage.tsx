import { PageHeader } from "@/components/PageHeader";
import { UsersTab } from "@/features/advanced/UsersTab";

export default function AdminUsersPage() {
  return (
    <div className="space-y-4">
      <PageHeader
        title="Người dùng & quota"
        desc="Quản lý tài khoản, quyền, quota câu hỏi và khoá/mở người dùng."
      />
      <UsersTab />
    </div>
  );
}
