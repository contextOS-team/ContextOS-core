/**
 * Background service worker for the ContextOS Chrome extension.
 *
 * Responsibilities:
 * - Receive ticket identifier messages from the content script.
 * - Store the current ticket identifier in chrome.storage.local.
 * - Respond to popup requests with context page data.
 * - Fetch context pages from the ContextOS backend API.
 */

const DEFAULT_BACKEND_URL = "http://localhost:8000";

// ---------------------------------------------------------------------------
// Storage helpers
// ---------------------------------------------------------------------------

async function getBackendUrl(): Promise<string> {
  const result = await chrome.storage.sync.get("backendUrl");
  return (result.backendUrl as string) || DEFAULT_BACKEND_URL;
}

async function getCurrentTicket(): Promise<string | null> {
  const result = await chrome.storage.local.get("currentTicket");
  return (result.currentTicket as string) || null;
}

async function setCurrentTicket(identifier: string | null): Promise<void> {
  await chrome.storage.local.set({ currentTicket: identifier });
}

async function getAuthToken(): Promise<string | null> {
  const result = await chrome.storage.local.get("authToken");
  return (result.authToken as string) || null;
}

// ---------------------------------------------------------------------------
// API communication
// ---------------------------------------------------------------------------

export interface ContextPageResponse {
  id: string;
  ticket_identifier: string;
  origin_story: string;
  business_requirements: string;
  technical_decisions: string;
  related_work: string;
  ai_prompt: string;
}

export interface FetchContextResult {
  status: "success" | "not_found" | "unauthorized" | "error";
  data?: ContextPageResponse;
  message?: string;
}

/**
 * Fetch the context page for a given ticket identifier from the backend API.
 *
 * @param identifier - Linear ticket identifier (e.g. "ENG-123")
 * @param token - Auth token (Supabase JWT or API key)
 * @returns Result object with status and optional context data
 */
export async function fetchContextPage(
  identifier: string,
  token: string
): Promise<FetchContextResult> {
  const backendUrl = await getBackendUrl();
  const url = `${backendUrl}/api/context/by-ticket/${encodeURIComponent(identifier)}`;

  try {
    const response = await fetch(url, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
    });

    if (response.ok) {
      const data = (await response.json()) as ContextPageResponse;
      return { status: "success", data };
    }

    if (response.status === 404) {
      return {
        status: "not_found",
        message: `No context page generated yet for ${identifier}`,
      };
    }

    if (response.status === 401 || response.status === 403) {
      return {
        status: "unauthorized",
        message: "Please log in to ContextOS first",
      };
    }

    const errorText = await response.text().catch(() => "");
    return {
      status: "error",
      message: `Backend error (${response.status}): ${errorText}`,
    };
  } catch (err) {
    return {
      status: "error",
      message:
        err instanceof Error
          ? `Cannot reach ContextOS backend: ${err.message}`
          : "Cannot reach ContextOS backend",
    };
  }
}

// ---------------------------------------------------------------------------
// Message handling
// ---------------------------------------------------------------------------

interface TicketDetectedMessage {
  type: "TICKET_DETECTED";
  identifier: string;
}

interface NoTicketMessage {
  type: "NO_TICKET";
}

interface GetContextMessage {
  type: "GET_CONTEXT";
}

interface GetCurrentTicketMessage {
  type: "GET_CURRENT_TICKET";
}

type ExtensionMessage =
  | TicketDetectedMessage
  | NoTicketMessage
  | GetContextMessage
  | GetCurrentTicketMessage;

chrome.runtime.onMessage.addListener(
  (
    message: ExtensionMessage,
    _sender: chrome.runtime.MessageSender,
    sendResponse: (response: unknown) => void
  ) => {
    switch (message.type) {
      case "TICKET_DETECTED":
        setCurrentTicket(message.identifier).then(() => {
          sendResponse({ ok: true, identifier: message.identifier });
        });
        return true; // async response

      case "NO_TICKET":
        setCurrentTicket(null).then(() => {
          sendResponse({ ok: true });
        });
        return true;

      case "GET_CURRENT_TICKET":
        getCurrentTicket().then((identifier) => {
          sendResponse({ identifier });
        });
        return true;

      case "GET_CONTEXT":
        handleGetContext().then(sendResponse);
        return true; // async response

      default:
        return false;
    }
  }
);

/**
 * Handle a GET_CONTEXT request from the popup.
 * Fetches the context page for the current ticket.
 */
async function handleGetContext(): Promise<FetchContextResult> {
  const identifier = await getCurrentTicket();

  if (!identifier) {
    return {
      status: "error",
      message: "No Linear ticket detected on the current page",
    };
  }

  const token = await getAuthToken();

  if (!token) {
    return {
      status: "unauthorized",
      message: "Please configure your API token in extension settings",
    };
  }

  return fetchContextPage(identifier, token);
}
