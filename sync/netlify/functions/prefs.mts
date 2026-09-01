import type { Config, Context } from "@netlify/functions";
import { getStore } from "@netlify/blobs";
import { apply, empty } from "./_state.mjs";

/* =====================================================================
   طبقة الحفظ للوحة «مركز المعرفة»
   ---------------------------------------------------------------------
   العطل الذي وُلدت منه: الإعجابات والمحفوظات كانت تعيش في localStorage
   لمتصفح واحد — لا تنتقل بين الجوال والماك، ويمسحها Safari بعد أسبوع،
   والمزامنة القديمة كانت تشترط لصق توكن GitHub في كل متصفح فلم تعمل قط.

   المبدأ: العميل يرسل «عمليات» صغيرة (أضف/احذف هذا الحفظ) لا حالته كاملة،
   فلا يدهس جهازٌ عملَ جهازٍ آخر، ولا حاجة إلى أرقام إصدارات ولا تصادم.

   كل كتابة تُبقي نسخة سابقة (٢٠ نسخة) فلا شيء يضيع بالخطأ.
   منطق الحالة في _state.mjs ليُختبر محليًا بلا نشر.
   ===================================================================== */

const STORE = "prefs";
const CURRENT = "state";
const HISTORY_MAX = 20;
const MAX_OPS = 500;

/* CORS مقصود هنا: اللوحة تعيش على نطاق آخر (GitHub Pages) وتنادي هذه الخدمة. */
const ALLOWED_ORIGINS = [
  "https://ddbb44-sudo.github.io",
  "http://127.0.0.1:8899",
  "http://localhost:8899",
];

function headers(origin: string | null) {
  const h: Record<string, string> = {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store",
    vary: "Origin",
    "access-control-allow-methods": "GET,POST,OPTIONS",
    "access-control-allow-headers": "content-type,x-key",
    "access-control-max-age": "86400",
  };
  if (origin && ALLOWED_ORIGINS.includes(origin)) h["access-control-allow-origin"] = origin;
  return h;
}

export default async (req: Request, _context: Context) => {
  const origin = req.headers.get("origin");
  const h = headers(origin);

  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: h });

  const store = getStore({ name: STORE, consistency: "strong" });

  if (req.method === "GET") {
    const state = (await store.get(CURRENT, { type: "json" })) || empty();
    return new Response(JSON.stringify(state), { status: 200, headers: h });
  }

  if (req.method !== "POST")
    return new Response(JSON.stringify({ error: "method" }), { status: 405, headers: h });

  const expected = Netlify.env.get("SYNC_KEY") || "";
  const given = req.headers.get("x-key") || new URL(req.url).searchParams.get("k") || "";
  if (expected && given !== expected)
    return new Response(JSON.stringify({ error: "key" }), { status: 401, headers: h });

  let body: any;
  try {
    body = await req.json();
  } catch {
    return new Response(JSON.stringify({ error: "json" }), { status: 400, headers: h });
  }

  const ops = Array.isArray(body?.ops) ? body.ops.slice(0, MAX_OPS) : [];
  if (!ops.length)
    return new Response(JSON.stringify({ error: "no-ops" }), { status: 400, headers: h });

  const state: any = (await store.get(CURRENT, { type: "json" })) || empty();
  const before = JSON.stringify(state);
  apply(state, ops);
  state.rev = (state.rev || 0) + 1;
  state.saved_at = new Date().toISOString();

  /* نسخة احتياطية قبل الكتابة — الاسترجاع ممكن دائمًا */
  if (before !== JSON.stringify(state)) {
    await store.set(`hist/${String(state.rev).padStart(6, "0")}`, before);
    const { blobs } = await store.list({ prefix: "hist/" });
    const keys = blobs.map((b) => b.key).sort();
    for (const k of keys.slice(0, Math.max(0, keys.length - HISTORY_MAX))) await store.delete(k);
  }

  await store.setJSON(CURRENT, state);
  return new Response(JSON.stringify(state), { status: 200, headers: h });
};

export const config: Config = { path: "/prefs" };
