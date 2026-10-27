/**
 * Bölüm H / FAZ 2: i18n bütünlük testleri.
 * 1) TR ve EN sözlükleri aynı anahtar kümesine sahip olmalı (eksik çeviri yok).
 * 2) Kaynakta t("...") ile kullanılan her anahtar iki dilde de tanımlı olmalı.
 */
import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

import { t, translations } from "../src/i18n";

const SRC = join(__dirname, "..", "src");

/** src altındaki tüm .ts/.tsx dosyalarını toplar. */
function walk(dir: string): string[] {
  const out: string[] = [];
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    const st = statSync(p);
    if (st.isDirectory()) out.push(...walk(p));
    else if (/\.(tsx?|jsx?)$/.test(name) && !name.endsWith(".test.ts")) out.push(p);
  }
  return out;
}

describe("i18n sözlük bütünlüğü", () => {
  it("TR ve EN aynı anahtar kümesine sahip", () => {
    const tr = Object.keys(translations.tr).sort();
    const en = Object.keys(translations.en).sort();
    const onlyTr = tr.filter((k) => !en.includes(k));
    const onlyEn = en.filter((k) => !tr.includes(k));
    expect(onlyTr, "sadece TR'de olan anahtarlar").toEqual([]);
    expect(onlyEn, "sadece EN'de olan anahtarlar").toEqual([]);
    expect(tr.length).toBeGreaterThan(50);
  });

  it("kaynakta kullanılan her t() anahtarı iki dilde de tanımlı", () => {
    const missing: Record<string, string[]> = {};
    for (const file of walk(SRC)) {
      const text = readFileSync(file, "utf-8");
      // t("...") ve t(`statik.${yerleske}`) sabit kullanımları yakala
      const re = /\bt\(\s*["'`]([^"'`$]+)["'`]\s*\)/g;
      let m: RegExpExecArray | null;
      while ((m = re.exec(text))) {
        const key = m[1];
        for (const lang of ["tr", "en"] as const) {
          if (!(key in translations[lang])) {
            (missing[key] ??= []).push(`${lang}:${file.split(/[\\/]/).pop()}`);
          }
        }
      }
    }
    expect(missing, "i18n'de eksik anahtarlar").toEqual({});
  });

  it("t() bilinmeyen anahtarda anahtarın kendisini döndürür (çökmez)", () => {
    expect(t("definitely.missing.key")).toBe("definitely.missing.key");
  });
});
