/** Misafirde kapatılmış özellik yuvası (Prompt 2).
 *
 * Yetkisi olmayan kullanıcıya gri bir alan + açıklayıcı tooltip gösterir;
 * içerik hiç mount edilmez, böylece ağ çağrısı da yapılmaz.
 */
import type { ReactNode } from "react";
import Card from "./Card";
import { t } from "../i18n";

export default function GuestLocked({
  title,
  allowed,
  children,
}: {
  title: string;
  allowed: boolean;
  children: ReactNode;
}) {
  if (allowed) return <>{children}</>;
  return (
    <Card title={title}>
      <div
        className="cursor-not-allowed rounded-lg border border-dashed px-3 py-4 text-center text-[11px] text-slate-500 opacity-70"
        title={t("guest.blocked")}
        aria-disabled="true"
      >
        🔒 {t("guest.blocked")}
      </div>
    </Card>
  );
}
