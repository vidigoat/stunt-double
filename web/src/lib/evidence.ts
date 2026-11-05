/** Verify a Stunt Double evidence record in the browser: every entry re-hashed and linked to the one before it, and the
 * head checked against the server's Ed25519 signature. Mirrors api/app/engine/evidence.py. */

type Entry = { seq: number; kind: string; body: unknown; prev: string; hash: string };
export type Sealed = { entries: Entry[]; head: string; signature: { public_key: string; signature: string; key_id: string } };
export type Check = { ok: boolean; entries: number; reason: string | null; badEntry?: number; where: "browser" | "server" };

const GENESIS = "0".repeat(64);

/** Python's json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False). */
export function canonical(v: unknown): string {
  if (Array.isArray(v)) return `[${v.map(canonical).join(",")}]`;
  if (v && typeof v === "object") {
    const o = v as Record<string, unknown>;
    return `{${Object.keys(o).sort().map((k) => `${JSON.stringify(k)}:${canonical(o[k])}`).join(",")}}`;
  }
  return JSON.stringify(v);
}

const hex = (b: ArrayBuffer) => [...new Uint8Array(b)].map((x) => x.toString(16).padStart(2, "0")).join("");
const bytes = (h: string) => new Uint8Array(h.match(/../g)!.map((x) => parseInt(x, 16)));
const b64 = (s: string) => Uint8Array.from(atob(s), (c) => c.charCodeAt(0));

async function sha256(s: string) {
  return hex(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s)));
}

export async function verifyInBrowser(sealed: Sealed, trustedKey: string): Promise<Check> {
  const n = sealed.entries.length;
  let prev = GENESIS;
  for (const [i, e] of sealed.entries.entries()) {
    if (e.seq !== i || e.prev !== prev) return { ok: false, entries: n, badEntry: i, where: "browser", reason: `step ${i + 1} (${e.kind}) is out of order or detached from the one before it` };
    if ((await sha256(canonical({ seq: i, kind: e.kind, body: e.body, prev }))) !== e.hash)
      return { ok: false, entries: n, badEntry: i, where: "browser", reason: `step ${i + 1} (${e.kind}) was changed after it was sealed` };
    prev = e.hash;
  }
  if (prev !== sealed.head) return { ok: false, entries: n, where: "browser", reason: "the head doesn't match the last step (steps were added or removed)" };
  if (sealed.signature.public_key !== trustedKey) return { ok: false, entries: n, where: "browser", reason: "signed by a different key than this server's" };
  const key = await crypto.subtle.importKey("raw", b64(trustedKey), { name: "Ed25519" }, false, ["verify"]);
  const ok = await crypto.subtle.verify({ name: "Ed25519" }, key, b64(sealed.signature.signature), bytes(prev));
  return ok ? { ok: true, entries: n, where: "browser", reason: null } : { ok: false, entries: n, where: "browser", reason: "the signature doesn't match" };
}
