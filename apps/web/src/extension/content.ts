/**
 * Content script injected on Linear pages.
 *
 * Extracts the ticket identifier from the URL (e.g. ENG-123) and sends
 * messages to the background service worker whenever the ticket changes.
 * Handles SPA navigation via popstate and MutationObserver on document.title.
 */

const LINEAR_TICKET_RE = /linear\.app\/[^/]+\/issue\/([A-Z]+-\d+)/;

/**
 * Extract a Linear ticket identifier from the current page URL.
 * Returns the identifier string (e.g. "ENG-123") or null if not on a ticket page.
 */
function extractTicketIdentifier(): string | null {
  const match = window.location.href.match(LINEAR_TICKET_RE);
  return match ? match[1] : null;
}

/** Last identifier we sent so we avoid duplicate messages. */
let lastIdentifier: string | null = null;

/**
 * Check the current URL for a ticket identifier and notify the background
 * service worker if it changed.
 */
function detectAndNotify(): void {
  const identifier = extractTicketIdentifier();

  if (identifier === lastIdentifier) {
    return;
  }

  lastIdentifier = identifier;

  if (identifier) {
    chrome.runtime.sendMessage({ type: "TICKET_DETECTED", identifier });
  } else {
    chrome.runtime.sendMessage({ type: "NO_TICKET" });
  }
}

// --- Initialization ---

// Run detection immediately on load.
detectAndNotify();

// Listen for SPA back/forward navigation.
window.addEventListener("popstate", () => detectAndNotify());

// Observe title changes as a proxy for SPA route transitions.
// Linear updates the document title on navigation, so this reliably
// catches in-app route changes that don't trigger popstate.
const titleObserver = new MutationObserver(() => detectAndNotify());

titleObserver.observe(document.querySelector("title") ?? document.head, {
  childList: true,
  subtree: true,
  characterData: true,
});

// Also listen for pushState/replaceState which Linear uses for SPA navigation.
// Wrap the native methods to dispatch a custom event we can listen for.
const originalPushState = history.pushState.bind(history);
const originalReplaceState = history.replaceState.bind(history);

history.pushState = function (...args: Parameters<typeof history.pushState>) {
  originalPushState(...args);
  detectAndNotify();
};

history.replaceState = function (
  ...args: Parameters<typeof history.replaceState>
) {
  originalReplaceState(...args);
  detectAndNotify();
};
