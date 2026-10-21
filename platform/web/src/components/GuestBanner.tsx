/** Kalıcı misafir banner'ı (Prompt 2): sohbetlerin kaydedilmediğini hatırlatır. */
import { clearGuestMode, isGuestMode } from "./LoginGate";
import { t } from "../i18n";

export default function GuestBanner() {
  if (!isGuestMode()) return null;
  return (
    <div
      role="status"
      className="relative z-20 flex items-center justify-between gap-3 border-b px-3 py-1.5 text-[11px] font-medium text-amber-200"
      style={{ borderColor: "var(--border)", background: "rgb(80 53 15 / 0.85)" }}
    >
      <span>{t("guest.banner")}</span>
      <button
        type="button"
        className="shrink-0 rounded border border-amber-300/30 px-2 py-0.5 text-[10px] hover:bg-amber-300/10"
        onClick={() => {
          clearGuestMode();
          location.reload();
        }}
      >
        {t("guest.exit")}
      </button>
    </div>
  );
}
