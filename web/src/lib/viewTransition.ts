/**
 * Shared-element names for the card → Reader morph (the app's one signature
 * transition). A `view-transition-name` must be unique among *visible* elements,
 * so both are keyed by item id — the grid card and the Reader it opens are the
 * only two places a given id appears.
 *
 * The id is interpolated into a CSS custom-ident, which may not start with a
 * digit, hence the `item-` prefix (ids are UUIDs and about half of them would
 * otherwise be invalid and silently drop the morph).
 */
export const vtThumb = (id: string) => `item-${id}-thumb`;
export const vtTitle = (id: string) => `item-${id}-title`;
