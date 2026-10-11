/**
 * Light up the inline chips that point at a source card while it's hovered,
 * and the card while one of its chips is (mockup: "hovering a chip lights its
 * card and vice versa"). DOM classes, not React state: the chips live inside
 * rendered markdown, and a re-render per hover would re-parse the answer.
 */
export function setCiteHot(anchorId: string, on: boolean): void {
  document.getElementById(anchorId)?.classList.toggle("cite-hot", on);
  document
    .querySelectorAll(`a.cite-chip[href="#${CSS.escape(anchorId)}"]`)
    .forEach((el) => el.classList.toggle("cite-hot", on));
}
