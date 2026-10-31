/**
 * KnowledgeCard — Özellik 8: kişisel bilgi tabanı (RAG).
 * Belge listesi + yükleme + durum (işleniyor/hazır/hata). Misafirde kapalı.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import Card from "./Card";
import { api } from "../api/client";
import { isGuestMode } from "./LoginGate";

interface Doc {
  id: number;
  name: string;
  chunks_count: number;
  status: string;
  error: string;
  created_at: string;
}

const STATUS_LABELS: Record<string, { text: string; color: string }> = {
  processing: { text: "işleniyor…", color: "rgb(250 204 21)" },
  ready: { text: "hazır", color: "rgb(74 222 128)" },
  error: { text: "hata", color: "rgb(248 113 113)" },
};

export default function KnowledgeCard() {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const guest = isGuestMode();

  const refresh = useCallback(async () => {
    try {
      setDocs((await api.knowledgeDocuments()).documents);
    } catch {
      /* offline */
    }
  }, []);

  useEffect(() => {
    if (!guest) void refresh();
  }, [guest, refresh]);

  const upload = async (file: File) => {
    const lower = file.name.toLowerCase();
    if (![".pdf", ".txt", ".md", ".docx"].some((ext) => lower.endsWith(ext))) {
      setError("Yalnızca PDF, TXT, MD, DOCX kabul edilir.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.knowledgeUpload(file);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Yükleme başarısız");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (doc: Doc) => {
    try {
      await api.knowledgeDelete(doc.id);
      await refresh();
    } catch {
      /* offline */
    }
  };

  if (guest) {
    return (
      <Card title="Bilgi Tabanı">
        <p className="py-3 text-center text-[11px] text-slate-500">
          Bu özellik misafir modunda kapalı — belgeleriniz hesabınıza özel
          saklanır. Giriş yapın.
        </p>
      </Card>
    );
  }

  return (
    <Card title="Bilgi Tabanı">
      <p className="mb-2 text-[10px] text-slate-500">
        PDF/TXT/MD/DOCX öğretin; JARVIS sohbette bu belgelerden yanıt verir.
      </p>
      <input
        ref={fileRef}
        type="file"
        accept=".pdf,.txt,.md,.docx"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) void upload(file);
          e.target.value = "";
        }}
      />
      <button
        type="button"
        onClick={() => fileRef.current?.click()}
        disabled={busy}
        className="btn-accent min-h-[44px] w-full rounded-lg py-2 text-xs font-semibold"
      >
        {busy ? "İşleniyor..." : "📄 Belge Yükle"}
      </button>
      {error && <p className="mt-1.5 text-[10px] text-rose-400">{error}</p>}
      <div className="mt-2 space-y-1">
        {docs.map((doc) => {
          const status = STATUS_LABELS[doc.status] ?? STATUS_LABELS.ready;
          return (
            <div
              key={doc.id}
              className="group flex items-center gap-2 rounded-lg border px-2 py-1.5 text-[11px]"
              style={{ borderColor: "var(--border)", background: "rgb(255 255 255 / 0.02)" }}
            >
              <span className="min-w-0 flex-1 truncate text-slate-200" title={doc.name}>
                📄 {doc.name}
              </span>
              <span className="text-[9px] text-slate-500">{doc.chunks_count} parça</span>
              <span className="text-[9px]" style={{ color: status.color }}>
                {doc.status === "error" ? doc.error.slice(0, 30) || status.text : status.text}
              </span>
              <button
                type="button"
                onClick={() => void remove(doc)}
                className="min-h-[32px] min-w-[32px] text-slate-600 opacity-0 hover:text-rose-400 group-hover:opacity-100"
                title="Belgeyi sil"
              >
                ✕
              </button>
            </div>
          );
        })}
        {docs.length === 0 && !busy && (
          <p className="py-2 text-center text-[10px] text-slate-500">
            Henüz belge yok.
          </p>
        )}
      </div>
    </Card>
  );
}
