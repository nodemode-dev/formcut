/**
 * The compact (phone) layout's condition. The desktop workspace needs 940px
 * across for its three panes' minimum widths, and a landscape phone has too
 * little height for the timeline under them, so either shortfall switches to
 * the stacked layout with bottom sheets. The stylesheets' @media rules use this
 * same text, and a test keeps the two identical.
 */
export const COMPACT = "(max-width: 940px), (max-height: 500px)";

export const compact = (): boolean => window.matchMedia(COMPACT).matches;
