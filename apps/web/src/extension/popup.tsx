/**
 * Extension popup entry point.
 *
 * Uses vanilla DOM manipulation (no React runtime dependency) to keep the
 * extension popup self-contained and lightweight. The .tsx extension is used
 * for TypeScript support only -- no JSX is emitted.
 *
 * Flow:
 * 1. Read current ticket identifier from chrome.storage.local.
 * 2. If no ticket, show "navigate to a Linear ticket" state.
 * 3. If ticket found, show loading then request context from background worker.
 * 4. Render context sections or appropriate error/empty states.
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ContextPageData {
  id: string;
  ticket_identifier: string;
  origin_story: string;
  business_requirements: string;
  technical_decisions: string;
  related_work: string;
  ai_prompt: string;
}

interface FetchContextResult {
  status: "success" | "not_found" | "unauthorized" | "error";
  data?: ContextPageData;
  message?: string;
}

// ---------------------------------------------------------------------------
// DOM helpers
// ---------------------------------------------------------------------------

function $(selector: string): HTMLElement | null {
  return document.querySelector(selector);
}

function el(
  tag: string,
  attrs?: Record<string, string>,
  ...children: (HTMLElement | string)[]
): HTMLElement {
  const element = document.createElement(tag);
  if (attrs) {
    for (const [key, value] of Object.entries(attrs)) {
      element.setAttribute(key, value);
    }
  }
  for (const child of children) {
    if (typeof child === "string") {
      element.appendChild(document.createTextNode(child));
    } else {
      element.appendChild(child);
    }
  }
  return element;
}

// ---------------------------------------------------------------------------
// Settings state
// ---------------------------------------------------------------------------

let settingsOpen = false;

// ---------------------------------------------------------------------------
// Render functions
// ---------------------------------------------------------------------------

function renderHeader(ticketId: string | null): HTMLElement {
  const titleSection = el(
    "div",
    {},
    el("div", { class: "header-title" }, "ContextOS"),
    ...(ticketId
      ? [el("div", { class: "header-ticket" }, ticketId)]
      : [])
  );

  const gearBtn = el("button", { class: "icon-btn", title: "Settings" });
  gearBtn.innerHTML = "&#9881;"; // gear icon
  gearBtn.addEventListener("click", () => {
    settingsOpen = !settingsOpen;
    const panel = $(".settings-panel");
    if (panel) {
      panel.style.display = settingsOpen ? "block" : "none";
    }
  });

  const actions = el("div", { class: "header-actions" }, gearBtn);

  const header = el("div", { class: "header" }, titleSection, actions);
  return header;
}

function renderSettings(): HTMLElement {
  const panel = el("div", { class: "settings-panel" });
  panel.style.display = "none";

  const tokenLabel = el("label", { class: "settings-label" }, "API Token");
  const tokenInput = el("input", {
    class: "settings-input",
    type: "password",
    placeholder: "Paste your ContextOS API token",
    id: "token-input",
  }) as HTMLInputElement;

  const backendLabel = el(
    "label",
    { class: "settings-label" },
    "Backend URL"
  );
  const backendInput = el("input", {
    class: "settings-input",
    type: "text",
    placeholder: "http://localhost:8000",
    id: "backend-input",
  }) as HTMLInputElement;

  const hint = el(
    "div",
    { class: "settings-hint" },
    "Get your API token from the ContextOS dashboard Settings page."
  );

  const saveBtn = el("button", { class: "btn btn-primary" }, "Save");
  saveBtn.addEventListener("click", async () => {
    const token = ($("#token-input") as HTMLInputElement)?.value?.trim();
    const backend = ($("#backend-input") as HTMLInputElement)?.value?.trim();

    if (token) {
      await chrome.storage.local.set({ authToken: token });
    }
    if (backend) {
      await chrome.storage.sync.set({ backendUrl: backend });
    }

    // Re-fetch context after saving token
    settingsOpen = false;
    panel.style.display = "none";
    await loadAndRender();
  });

  panel.append(tokenLabel, tokenInput, hint, backendLabel, backendInput, saveBtn);

  // Load existing values
  chrome.storage.local.get("authToken").then((result) => {
    if (result.authToken) {
      tokenInput.value = result.authToken as string;
    }
  });
  chrome.storage.sync.get("backendUrl").then((result) => {
    if (result.backendUrl) {
      backendInput.value = result.backendUrl as string;
    }
  });

  return panel;
}

function renderState(
  icon: string,
  title: string,
  message: string,
  actionBtn?: HTMLElement
): HTMLElement {
  const container = el("div", { class: "state-container" });
  const iconEl = el("div", { class: "state-icon" }, icon);
  const titleEl = el("div", { class: "state-title" }, title);
  const messageEl = el("div", { class: "state-message" }, message);
  container.append(iconEl, titleEl, messageEl);
  if (actionBtn) {
    actionBtn.style.marginTop = "12px";
    container.appendChild(actionBtn);
  }
  return container;
}

function renderLoading(): HTMLElement {
  const container = el("div", { class: "state-container" });
  const spinner = el("div", { class: "spinner" });
  const msg = el("div", { class: "state-message" }, "Loading context...");
  container.append(spinner, msg);
  return container;
}

function renderContextSections(data: ContextPageData): HTMLElement {
  const content = el("div", { class: "content" });

  const sections: Array<{ title: string; body: string }> = [
    { title: "Origin Story", body: data.origin_story },
    { title: "Business Requirements", body: data.business_requirements },
    { title: "Technical Decisions", body: data.technical_decisions },
    { title: "Related Work", body: data.related_work },
    { title: "AI Prompt", body: data.ai_prompt },
  ];

  for (const section of sections) {
    if (!section.body) continue;
    const card = el(
      "div",
      { class: "card" },
      el("div", { class: "card-title" }, section.title),
      el("div", { class: "card-body" }, section.body)
    );
    content.appendChild(card);
  }

  return content;
}

function renderFooter(ticketId: string | null): HTMLElement {
  const footer = el("div", { class: "footer" });
  if (ticketId) {
    const link = el(
      "a",
      {
        href: "#",
        title: "Open in ContextOS dashboard",
      },
      "Open in Dashboard"
    );
    link.addEventListener("click", async (e) => {
      e.preventDefault();
      const result = await chrome.storage.sync.get("backendUrl");
      const baseUrl = (result.backendUrl as string) || "http://localhost:3000";
      // Dashboard URL uses the Next.js app, which typically runs on port 3000
      const dashUrl = baseUrl.replace(":8000", ":3000");
      chrome.tabs.create({
        url: `${dashUrl}/dashboard/context/${ticketId}`,
      });
    });
    footer.appendChild(link);
  }
  return footer;
}

// ---------------------------------------------------------------------------
// Main render logic
// ---------------------------------------------------------------------------

const root = $("#root")!;

async function loadAndRender(): Promise<void> {
  // Clear existing content
  root.innerHTML = "";

  // Get current ticket from storage
  const ticketResult = await chrome.storage.local.get("currentTicket");
  const ticketId = (ticketResult.currentTicket as string) || null;

  // Render header + settings (always present)
  root.appendChild(renderHeader(ticketId));
  root.appendChild(renderSettings());

  // No ticket detected
  if (!ticketId) {
    root.appendChild(
      renderState(
        "\uD83D\uDD17", // link emoji
        "No ticket detected",
        "Navigate to a Linear ticket page to see context."
      )
    );
    return;
  }

  // Show loading while fetching
  const loadingEl = renderLoading();
  root.appendChild(loadingEl);

  // Request context from background worker
  const result: FetchContextResult = await new Promise((resolve) => {
    chrome.runtime.sendMessage({ type: "GET_CONTEXT" }, resolve);
  });

  // Remove loading
  loadingEl.remove();

  switch (result.status) {
    case "success":
      if (result.data) {
        root.appendChild(renderContextSections(result.data));
      }
      break;

    case "not_found":
      root.appendChild(
        renderState(
          "\uD83D\uDCCB", // clipboard emoji
          `No context page yet`,
          `No context page generated yet for ${ticketId}. Generate one from the ContextOS dashboard.`
        )
      );
      break;

    case "unauthorized": {
      const loginBtn = el(
        "button",
        { class: "btn btn-primary" },
        "Configure Token"
      );
      loginBtn.addEventListener("click", () => {
        settingsOpen = true;
        const panel = $(".settings-panel");
        if (panel) panel.style.display = "block";
      });
      root.appendChild(
        renderState(
          "\uD83D\uDD12", // lock emoji
          "Authentication required",
          result.message || "Please log in to ContextOS first.",
          loginBtn
        )
      );
      break;
    }

    case "error": {
      const retryBtn = el("button", { class: "btn btn-secondary" }, "Retry");
      retryBtn.addEventListener("click", () => loadAndRender());
      root.appendChild(
        renderState(
          "\u26A0\uFE0F", // warning emoji
          "Connection error",
          result.message || "Cannot reach ContextOS backend.",
          retryBtn
        )
      );
      break;
    }
  }

  // Footer with dashboard link
  root.appendChild(renderFooter(ticketId));
}

// Run on popup open
loadAndRender();
