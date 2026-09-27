import { Alert } from "@/components/Alert";
import { PageHeader } from "@/components/PageHeader";
import { Spinner } from "@/components/Spinner";
import { PasswordSection } from "@/features/settings/PasswordSection";
import { PrivacySection } from "@/features/settings/PrivacySection";
import { ProfileSection } from "@/features/settings/ProfileSection";
import { useMe } from "@/features/settings/useMe";

/** Cài đặt tài khoản của chính người dùng (mọi role): hồ sơ, mật khẩu, quyền riêng tư. */
export default function SettingsPage() {
  const me = useMe();

  return (
    <main className="h-full overflow-y-auto">
      <div className="mx-auto max-w-3xl space-y-6 px-6 py-8 lg:px-8">
        <PageHeader title="Cài đặt"/>
        {me.isPending ? (
          <Spinner />
        ) : me.isError ? (
          <Alert>Không tải được thông tin tài khoản, thử lại sau.</Alert>
        ) : (
          <>
            <ProfileSection user={me.data} />
            {me.data.has_password && <PasswordSection />}
            <PrivacySection user={me.data} />
          </>
        )}
      </div>
    </main>
  );
}
