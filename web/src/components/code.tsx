import { cn } from "@/lib/utils";

/** A tiny, dependency-free highlighter for the short Python / shell / JSON snippets on dark code blocks. */
const RULES: [RegExp, string][] = [
  [/^#[^\n]*|(?<=\s)#[^\n]*/, "text-[#8A8A85]"],                          // comments
  [/^"(?:[^"\\\n]|\\.)*"|^'(?:[^'\\\n]|\\.)*'/, "text-[#7EE2A8]"],        // strings
  [/^@[\w.]+/, "text-[#FFB86B]"],                                          // decorators
  [/^\b(?:def|from|import|return|print|for|in|if|not|None|True|False)\b/, "text-[#8AB4FF]"],
  [/^\$ |^> /, "text-[#8AB4FF]"],                                          // prompts
  [/^\b\d[\d.,]*\b/, "text-[#F5C2E7]"],                                    // numbers
];

function tokenize(src: string): { t: string; c?: string }[] {
  const out: { t: string; c?: string }[] = [];
  let i = 0;
  let plain = "";
  while (i < src.length) {
    const rest = src.slice(i);
    const atLineStart = i === 0 || src[i - 1] === "\n";
    let hit: { t: string; c: string } | null = null;
    for (const [re, c] of RULES) {
      if ((re.source.startsWith("^\\$") || re.source.startsWith("^#")) && !atLineStart && !/^#/.test(rest)) continue;
      const m = re.exec(rest);
      if (m && m.index === 0 && m[0]) { hit = { t: m[0], c }; break; }
    }
    if (hit && /^\w/.test(hit.t) && i > 0 && /\w/.test(src[i - 1])) hit = null; // keyword inside an identifier
    if (hit) {
      if (plain) { out.push({ t: plain }); plain = ""; }
      out.push(hit);
      i += hit.t.length;
    } else {
      plain += src[i];
      i += 1;
    }
  }
  if (plain) out.push({ t: plain });
  return out;
}

export function Code({ code, className }: { code: string; className?: string }) {
  return (
    <pre className={cn("overflow-x-auto rounded-xl bg-foreground p-5 font-mono text-[13px] leading-relaxed text-background", className)}>
      {tokenize(code).map((tok, i) => (tok.c ? <span key={i} className={tok.c}>{tok.t}</span> : tok.t))}
    </pre>
  );
}
