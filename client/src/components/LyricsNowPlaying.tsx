import * as React from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Eye, EyeOff, Pause, Play } from "lucide-react";

type LyricsNowPlayingProps = {
  lyrics?: string;
  src?: string;

  className?: string;

  autoPlay?: boolean;
  loop?: boolean;

  /** 12 => ~5s per line */
  linesPerMinute?: number;

  /** Fade duration (ms) */
  fadeMs?: number;

  /** Mask fade (Option B) */
  maskFadeStartPercent?: number; // 94–98
  maskFadeEndPercent?: number;   // usually 100
};

function parseLyricsToLines(text: string) {
  return text
    .replace(/\r\n/g, "\n")
    .split("\n")
    .map((l) => l.trimEnd())
    .filter((l) => l.trim().length > 0);
}

export function LyricsNowPlaying({
  lyrics,
  src,
  className = "",
  autoPlay = true,
  loop = true,
  linesPerMinute = 12,
  fadeMs = 320,
  maskFadeStartPercent = 96,
  maskFadeEndPercent = 105,
}: LyricsNowPlayingProps) {
  const [loadedLyrics, setLoadedLyrics] = React.useState<string | null>(lyrics ?? null);
  const [loading, setLoading] = React.useState(false);

  // Always start shown, and reset to shown when source/lyrics changes
  const [hidden, setHidden] = React.useState(false);

  const [playing, setPlaying] = React.useState(autoPlay);
  const lastWasPlayingRef = React.useRef(autoPlay);

  // Text + fade state
  const [lines, setLines] = React.useState<string[]>([]);
  const [index, setIndex] = React.useState(0);
  const [text, setText] = React.useState("");
  const [opacity, setOpacity] = React.useState(1);

  // Load lyrics from prop or src
  React.useEffect(() => {
    // Reset visibility every time content source changes (fixes "loads hidden")
    setHidden(false);
    setPlaying(autoPlay);
    lastWasPlayingRef.current = autoPlay;

    if (typeof lyrics === "string") {
      setLoadedLyrics(lyrics);
      return;
    }
    if (!src) return;

    const controller = new AbortController();
    setLoading(true);

    fetch(src, { signal: controller.signal })
      .then(async (r) => {
        if (!r.ok) throw new Error(`Failed to load lyrics (${r.status})`);
        return r.text();
      })
      .then((t) => setLoadedLyrics(t))
      .catch((err) => {
        console.warn("[LyricsNowPlaying] lyrics fetch failed:", err);
        setLoadedLyrics(null);
      })
      .finally(() => setLoading(false));

    return () => controller.abort();
  }, [lyrics, src, autoPlay]);

  // Parse into lines + initialize first line (visible!)
  React.useEffect(() => {
    const nextLines = loadedLyrics ? parseLyricsToLines(loadedLyrics) : [];
    setLines(nextLines);

    setIndex(0);
    setOpacity(1);

    if (nextLines.length > 0) setText(nextLines[0]);
    else setText("");
  }, [loadedLyrics]);

  const intervalMs = Math.max(250, Math.round(60_000 / Math.max(1, linesPerMinute)));

  // Advance line-by-line with simple fade out -> swap -> fade in
  React.useEffect(() => {
    if (!playing) return;
    if (hidden) return;
    if (lines.length === 0) return;

    const t = window.setTimeout(() => {
      const next = index + 1;
      const nextIndex = next < lines.length ? next : loop ? 0 : index;

      if (nextIndex === index && !loop) {
        setPlaying(false);
        return;
      }

      // fade out
      setOpacity(0);

      // swap text near the end of fade
      const swap = window.setTimeout(() => {
        setIndex(nextIndex);
        setText(lines[nextIndex] ?? "");
        // fade in next frame
        requestAnimationFrame(() => setOpacity(1));
      }, Math.max(20, Math.floor(fadeMs * 0.7)));

      return () => window.clearTimeout(swap);
    }, intervalMs);

    return () => window.clearTimeout(t);
  }, [playing, hidden, lines, index, loop, intervalMs, fadeMs]);

  const togglePlay = () => {
    if (lines.length === 0) return;
    if (hidden) return; // require show first
    setPlaying((p) => !p);
  };

  const toggleHidden = () => {
    setHidden((h) => {
      const next = !h;
      if (next) {
        lastWasPlayingRef.current = playing;
        setPlaying(false);
      } else {
        setPlaying(lastWasPlayingRef.current);
      }
      return next;
    });
  };

  const mask = `linear-gradient(to right, black ${maskFadeStartPercent}%, transparent ${maskFadeEndPercent}%)`;

  const displayText =
    hidden
      ? "Lyrics hidden"
      : lines.length === 0
        ? loading
          ? "Loading lyrics…"
          : "No lyrics (check src path)"
        : text;


  const outerRef = React.useRef<HTMLSpanElement | null>(null);
  const innerRef = React.useRef<HTMLSpanElement | null>(null);

  const [needsScroll, setNeedsScroll] = React.useState(false);
  const [scrollPx, setScrollPx] = React.useState(0);

  // stable unique animation name per component instance
  const animName = React.useId().replace(/[:]/g, "");

  const reduceMotion =
    typeof window !== "undefined" &&
    window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Measure overflow whenever the displayed text changes (or size changes)
  React.useLayoutEffect(() => {
    const measure = () => {
      const outer = outerRef.current;
      const inner = innerRef.current;
      if (!outer || !inner) return;

      // Reset any previous transform so measurements are accurate
      inner.style.transform = "translateX(0px)";

      const ow = outer.clientWidth;
      const iw = inner.scrollWidth;

      const overflow = Math.max(0, iw - ow);
      setNeedsScroll(overflow > 4); // small tolerance
      setScrollPx(overflow);
    };

    measure();

    // Re-measure on resize
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(measure) : null;
    if (ro && outerRef.current) ro.observe(outerRef.current);

    window.addEventListener("resize", measure);
    return () => {
      window.removeEventListener("resize", measure);
      ro?.disconnect();
    };
  }, [displayText]);


  return (
    <Card className={["rounded-xl border bg-card/50 px-2 py-1 shadow-sm", className].join(" ")}>
      <div className="flex items-center gap-2">
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="h-7 w-7 rounded-lg"
          onClick={togglePlay}
          disabled={lines.length === 0 || hidden}
          aria-label={playing ? "Pause lyrics" : "Play lyrics"}
        >
          {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
        </Button>

        <button
          type="button"
          className="min-w-0 flex-1 text-left"
          onClick={togglePlay}
          disabled={lines.length === 0 || hidden}
          aria-label="Lyrics ticker"
          title={hidden ? "" : displayText}
        >
                    <span
            ref={outerRef}
            className="block overflow-hidden text-sm text-muted-foreground"
            style={{
              opacity: hidden || lines.length === 0 ? 1 : opacity,
              transition: `opacity ${fadeMs}ms ease`,
              WebkitMaskImage: mask,
              maskImage: mask,
            }}
          >
            {/* keyframes only matter if we actually need to scroll */}
            {needsScroll && !reduceMotion ? (
              <style>{`
                @keyframes lyrics-marquee-${animName} {
                  0%   { transform: translateX(0px); }
                  10%  { transform: translateX(0px); }  /* hold at start */
                  90%  { transform: translateX(-${scrollPx}px); }
                  100% { transform: translateX(-${scrollPx}px); } /* hold at end */
                }
              `}</style>
            ) : null}

            <span
              ref={innerRef}
              className="inline-block whitespace-nowrap will-change-transform"
              style={{
                // Only animate if it overflows and we’re actively “playing” and visible
                animation:
                  !hidden && playing && needsScroll && !reduceMotion
                    ? `lyrics-marquee-${animName} ${Math.max(
                        2.5,
                        // speed-based duration, but cap so it fits into your line interval nicely
                        Math.min(scrollPx / 40, Math.max(2.5, intervalMs / 1000 - 0.6))
                      )}s linear infinite`
                    : undefined,
              }}
            >
              {displayText || "\u00A0"}
            </span>
          </span>

        </button>

        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="h-7 w-7 rounded-lg"
          onClick={toggleHidden}
          disabled={lines.length === 0 && !loading}
          aria-label={hidden ? "Show lyrics" : "Hide lyrics"}
        >
          {hidden ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
        </Button>
      </div>
    </Card>
  );
}
