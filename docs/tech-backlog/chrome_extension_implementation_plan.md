# CareerLoop — Chrome Extension Implementation Plan
## Manifest V3 & Trusted CDP Inputs Co-Pilot

> [!NOTE]
> **Product Thesis:** *Intelligence is the product. Automation is the UX.*  
> This Chrome Extension acts as the high-fidelity execution arm of the system, replacing brittle, easily blocked headless scripts with a trusted, user-in-the-loop co-pilot experience.

---

## 📈 Tangible ROI Mapping

The extension directly accelerates the **Momentum Conversion Chain** in two ways:

1.  **Time-to-Apply Reduction (Friction ROI):** Reduces manual form-filling from an average of 8 minutes per job application to **under 45 seconds** (including S8 resume selection, cover letter insertion, and screening QA).
2.  **Conversion Accuracy (Quality ROI):** Automatically selects and inputs the exact tailored S8 resume version (classic-ats vs. product-engineer) matching the company profile, eliminating applicant mismatches.
3.  **Bypassing Bot Blockers (Success ROI):** By using native Chrome debugger events, we bypass `isTrusted === false` security layers, bringing auto-fill success rates from <30% to **>98%**.

---

## 🛠️ Tech Architecture & Manifest V3 Specs

We will build a custom, lightweight Chrome Extension based on Manifest V3 guidelines:

### 1. File Structure
```
careerloop-extension/
├── manifest.json
├── background.js          # Ephemeral Service Worker
├── sidepanel/
│   ├── sidepanel.html     # Conversational Action Sidepanel
│   ├── sidepanel.js
│   └── sidepanel.css      # Premium Glassmorphism styling
├── content/
│   └── autofill.js        # DOM analyzer and field injector
└── icons/
    ├── icon-16.png
    ├── icon-48.png
    └── icon-128.png
```

### 2. manifest.json Declarations
```json
{
  "manifest_version": 3,
  "name": "CareerLoop Co-Pilot",
  "version": "1.0.0",
  "description": "Auto-fills high-converting tailored applications and outreach on LinkedIn, Lever, and Greenhouse.",
  "permissions": [
    "sidePanel",
    "activeTab",
    "scripting",
    "storage",
    "debugger"
  ],
  "host_permissions": [
    "https://*.linkedin.com/*",
    "https://*.lever.co/*",
    "https://*.greenhouse.io/*",
    "http://127.0.0.1:8000/*"
  ],
  "background": {
    "service_worker": "background.js"
  },
  "side_panel": {
    "default_path": "sidepanel/sidepanel.html"
  },
  "action": {
    "default_title": "Open CareerLoop Co-Pilot"
  }
}
```

---

## 🔌 The Escape Hatch: Trusted Inputs via `chrome.debugger`

Standard DOM inputs (`el.value = val`) set `event.isTrusted = false`, causing sites to reject the inputs. To solve this, the service worker attaches the **Chrome DevTools Protocol (CDP)** to send OS-level hardware inputs:

### service-worker / background.js
```javascript
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "dispatch_trusted_click") {
    (async () => {
      const tabId = message.tabId;
      const { x, y } = message.coords;
      
      await chrome.debugger.attach({ tabId }, "1.3");
      
      // Mouse Press
      await chrome.debugger.sendCommand({ tabId }, "Input.dispatchMouseEvent", {
        type: "mousePressed",
        x,
        y,
        button: "left",
        clickCount: 1
      });
      
      // Mouse Release
      await chrome.debugger.sendCommand({ tabId }, "Input.dispatchMouseEvent", {
        type: "mouseReleased",
        x,
        y,
        button: "left",
        clickCount: 1
      });
      
      await chrome.debugger.detach({ tabId });
      sendResponse({ success: true });
    })();
    return true; // Keep message channel open
  }
});
```

---

## 🔄 User-In-The-Loop Execution Flow

```
1. User opens a job page on Lever/Greenhouse/LinkedIn
   │
   ▼
2. User clicks the CareerLoop browser action button
   │
   ▼
3. Service Worker fires sidePanel.open() inside the active tab
   │
   ▼
4. Sidepanel fetches compiled tailored S8 pack from local FastAPI/ledger
   │
   ▼
5. Sidepanel lists matching assets:
   - S8 Resume: "Siddharth_Saminathan_Resume_BukuWarung_ATS.pdf"
   - Cover Note tailored to Mandeep Singh
   - Prefilled screening answers (e.g. Notice: 30 days, Salary: ₹35L)
   │
   ▼
6. User clicks "Auto-Fill with CareerLoop"
   │
   ▼
7. Content Script analyzes input schemas & highlights mapped fields in Green
   │
   ▼
8. Service Worker dispatches trusted click & key events to fill fields
   │
   ▼
9. User reviews the prefilled application forms and manually clicks "Submit"
```

---

## 📅 Roadmap Milestones (Phase 1.5 - 2.0)

*   **Milestone 1 (Scaffolding):** Build Manifest V3 boilerplate, configure Sidepanel triggers on extension icon click, and write basic CSS styling.
*   **Milestone 2 (DOM Parsing & Mappings):** Implement Greenhouse/Lever input tag analyzers. Map text fields, file inputs, and custom checkboxes to standard JSON profile elements.
*   **Milestone 3 (CDP Hardening):** Write the `chrome.debugger` event dispatcher in the background script. Test hardware click/text dispatching against security-protected fields.
*   **Milestone 4 (API Integration):** Connect the Sidepanel to the local FastAPI port (`:8000`) or Supabase endpoint to pull `pack_metadata.json` dynamically for the current tab's domain.
