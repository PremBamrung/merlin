import { useEffect, useRef, useState } from "react";

/**
 * The script-driven half of the motion packs (styles/motion.css is the rest):
 * the ★ gold-leaf burst, the thumbnail → drawer morph, count-up numbers and
 * the self-typing title. Each one checks reduced motion itself — the CSS kill
 * switch can't reach Web Animations or requestAnimationFrame.
 */

export function reducedMotion(): boolean {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

const EASE_OUT = "cubic-bezier(.16, 1, .3, 1)";

/** Gold leaf flies out of `el` — the ★ save. Six flakes, ~600ms, gone. */
export function leafBurst(el: Element | null): void {
  if (!el || reducedMotion()) return;
  const r = el.getBoundingClientRect();
  const cx = r.left + r.width / 2;
  const cy = r.top + r.height / 2;
  for (let i = 0; i < 6; i++) {
    const leaf = document.createElement("span");
    leaf.className = "m-leaf";
    leaf.style.left = `${cx - 3}px`;
    leaf.style.top = `${cy - 1.5}px`;
    document.body.appendChild(leaf);
    const angle = (i / 6) * Math.PI * 2 + Math.random() * 0.6;
    const dist = 16 + Math.random() * 10;
    const spin = (Math.random() - 0.5) * 240;
    leaf
      .animate(
        [
          { transform: "translate(0,0) rotate(0deg) scale(1)", opacity: 1 },
          {
            transform: `translate(${Math.cos(angle) * dist}px, ${Math.sin(angle) * dist + 6}px) rotate(${spin}deg) scale(.6)`,
            opacity: 0,
          },
        ],
        { duration: 560 + Math.random() * 120, easing: EASE_OUT, fill: "forwards" },
      )
      .finished.then(() => leaf.remove(), () => leaf.remove());
  }
}

/**
 * Open item: the thumbnail you clicked flies into the drawer's hero. The card
 * records itself as the origin on click; the drawer plays the flight when its
 * hero image is in place. A stale origin (> 1.5s old) is ignored.
 */
let origin: { img: HTMLImageElement; at: number } | null = null;

export function setMorphOrigin(img: HTMLImageElement | null | undefined): void {
  origin = img ? { img, at: performance.now() } : null;
}

/** Returns true when a morph played (the caller can stagger its own fade). */
export function playMorph(to: HTMLImageElement | null): boolean {
  const from = origin;
  origin = null;
  if (!from || !to || reducedMotion() || performance.now() - from.at > 1500) return false;
  if (!from.img.isConnected) return false;
  const a = from.img.getBoundingClientRect();
  const b = to.getBoundingClientRect();
  if (!a.width || !b.width) return false;
  const ghost = document.createElement("img");
  ghost.src = from.img.currentSrc || from.img.src;
  ghost.className = "m-morph-ghost";
  Object.assign(ghost.style, {
    left: `${a.left}px`,
    top: `${a.top}px`,
    width: `${a.width}px`,
    height: `${a.height}px`,
    borderRadius: "10px",
  });
  document.body.appendChild(ghost);
  to.style.visibility = "hidden";
  const done = () => {
    to.style.visibility = "";
    ghost.remove();
  };
  ghost
    .animate(
      [
        { left: `${a.left}px`, top: `${a.top}px`, width: `${a.width}px`, height: `${a.height}px`, borderRadius: "10px" },
        { left: `${b.left}px`, top: `${b.top}px`, width: `${b.width}px`, height: `${b.height}px`, borderRadius: "12px" },
      ],
      { duration: 460, easing: "cubic-bezier(.2,.8,.2,1)", fill: "forwards" },
    )
    .finished.then(done, done);
  return true;
}

/** A number that counts up from 0 the first time it scrolls into view. */
export function useCountUp(
  target: number,
  duration = 700,
): [React.RefObject<HTMLSpanElement | null>, number] {
  const ref = useRef<HTMLSpanElement | null>(null);
  const [still] = useState(reducedMotion);
  const [value, setValue] = useState(0);
  const [done, setDone] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (still || done || !el) return;
    let raf = 0;
    const io = new IntersectionObserver((entries) => {
      if (!entries.some((e) => e.isIntersecting)) return;
      io.disconnect();
      const t0 = performance.now();
      const step = (t: number) => {
        const p = Math.min(1, (t - t0) / duration);
        setValue(Math.round(target * (1 - Math.pow(1 - p, 3))));
        if (p < 1) raf = requestAnimationFrame(step);
        else setDone(true);
      };
      raf = requestAnimationFrame(step);
    });
    io.observe(el);
    return () => {
      io.disconnect();
      cancelAnimationFrame(raf);
    };
  }, [target, duration, still, done]);
  // Once it has counted (or never animates), it simply shows the number.
  return [ref, still || done ? target : value];
}

/**
 * Types `text` in when it *arrives* — goes from empty to a value while the
 * component is mounted (the server naming a new thread). A value present on
 * mount, or any later change, is shown at once.
 */
export function useTypewriter(text: string | null): { shown: string; typing: boolean } {
  const [prev, setPrev] = useState(text);
  const [typed, setTyped] = useState<{ text: string; n: number } | null>(null);
  // Render-time "adjust state on prop change": start typing only on arrival.
  if (text !== prev) {
    setPrev(text);
    setTyped(!prev && text && !reducedMotion() ? { text, n: 0 } : null);
  }
  useEffect(() => {
    if (!typed || typed.n >= typed.text.length) return;
    const id = window.setTimeout(() => setTyped((t) => (t ? { ...t, n: t.n + 1 } : t)), 28);
    return () => window.clearTimeout(id);
  }, [typed]);
  const typing = !!typed && typed.n < typed.text.length;
  return { shown: typing ? typed!.text.slice(0, typed!.n) : (text ?? ""), typing };
}
