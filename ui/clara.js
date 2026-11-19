// Sierra Valley Health demo: page behavior. Loaded once through launch(head=...).
// Script tags inside gr.HTML don't run, so everything lives here, on delegated listeners.
(function () {
  "use strict";
  if (window.__svhClara) return;
  window.__svhClara = true;

  const $ = (sel) => document.querySelector(sel);

  const init = () => {
    const params = new URLSearchParams(location.search);
    if (params.get("presenter") === "1") setPresenter(true);
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();

  // Hash router: "#/slug" shows that inner page; "#/" or "" shows home; any other "#id" shows
  // home and scrolls to that section. Header, footer and the Clara drawer never unmount.
  function route() {
    const hash = location.hash || "#/";
    const pages = document.querySelectorAll(".svh-page[data-route]");
    if (!pages.length) return;
    let slug = hash.startsWith("#/") ? hash.slice(2) || "home" : "home";
    if (!document.querySelector(`.svh-page[data-route="${CSS.escape(slug)}"]`)) slug = "home";
    pages.forEach((p) => { p.hidden = p.dataset.route !== slug; });
    document.querySelectorAll(".svh-nav a").forEach((a) => {
      a.toggleAttribute("aria-current", a.getAttribute("href") === hash);
    });
    if (slug !== "home") {
      window.scrollTo(0, 0);
      const title = document.querySelector(`.svh-page[data-route="${slug}"] .svh-page-title`);
      if (title) title.focus({ preventScroll: true });
    } else if (!hash.startsWith("#/")) {
      const target = document.getElementById(hash.slice(1));
      if (target) target.scrollIntoView();
    } else {
      window.scrollTo(0, 0);
    }
  }
  window.addEventListener("hashchange", route);
  // gr.HTML renders after this script runs, so route once the homepage is in the DOM.
  const waitForPage = new MutationObserver(() => {
    if (document.querySelector(".svh-page[data-route]")) { waitForPage.disconnect(); route(); }
  });
  waitForPage.observe(document.documentElement, { childList: true, subtree: true });

  function chatInput() { return $("#clara-input textarea"); }

  function openDrawer(focusInput = true) {
    document.body.classList.add("clara-open");
    const drawer = $("#clara-drawer");
    if (drawer) drawer.setAttribute("aria-hidden", "false");
    if (focusInput) setTimeout(() => chatInput() && chatInput().focus(), 160);
  }

  function closeDrawer() {
    stopVoice();
    document.body.classList.remove("clara-open");
    const drawer = $("#clara-drawer");
    if (drawer) drawer.setAttribute("aria-hidden", "true");
    const launcher = $(".svh-launcher");
    if (launcher) launcher.focus();
  }

  function setPresenter(on) {
    document.body.classList.toggle("presenter", on);
    document.querySelectorAll("[data-presenter-toggle]").forEach((b) => b.setAttribute("aria-pressed", String(on)));
  }

  // One code path for every entry point: write the prompt into the chat box, then press Send.
  function sendToClara(prompt) {
    openDrawer(false);
    const box = chatInput();
    const send = $("#clara-send");
    if (!box || !send) return;
    const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value").set;
    setter.call(box, prompt);
    box.dispatchEvent(new Event("input", { bubbles: true }));
    setTimeout(() => send.click(), 60);
  }

  // ---------- Channels: one agent, several doors ----------
  const CHANNEL_LABELS = { web: "Web chat", voice: "Phone call with Clara", sms: "Text message · Sierra Valley Health", portal: "MySierra portal · signed in" };
  let channel = "web";

  function setChannel(ch) {
    channel = CHANNEL_LABELS[ch] ? ch : "web";
    const box = $("#clara-channel textarea") || $("#clara-channel input");
    const btn = $("#clara-channel-set");
    if (!box || !btn) return;
    const proto = box.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, "value").set.call(box, channel);
    box.dispatchEvent(new Event("input", { bubbles: true }));
    setTimeout(() => btn.click(), 80);
    Object.keys(CHANNEL_LABELS).forEach((c) => document.body.classList.toggle(`channel-${c}`, c === channel));
    document.querySelectorAll("[data-channel-label]").forEach((el) => { el.textContent = CHANNEL_LABELS[channel]; });
    if (channel !== "voice") stopVoice();
    lastSpoken = "";
    openDrawer(channel !== "voice");
  }

  // Voice: the browser's own speech recognition (patient) and speech synthesis (Clara). Free, no keys.
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recognizer = null;
  let lastSpoken = "";

  function micLabel(text, on) {
    document.querySelectorAll("[data-mic-label]").forEach((el) => { el.textContent = text; });
    document.querySelectorAll("[data-voice-mic]").forEach((b) => b.setAttribute("aria-pressed", String(!!on)));
  }

  function listen() {
    if (!Recognition) { micLabel("Voice input needs Chrome; type instead", false); return; }
    if (recognizer) { recognizer.stop(); return; }
    window.speechSynthesis && window.speechSynthesis.cancel();
    recognizer = new Recognition();
    recognizer.lang = "en-US";
    recognizer.interimResults = true;
    micLabel("Listening…", true);
    recognizer.onresult = (e) => {
      const result = e.results[e.results.length - 1];
      const box = chatInput();
      if (box) {
        Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value").set.call(box, result[0].transcript);
        box.dispatchEvent(new Event("input", { bubbles: true }));
      }
      if (result.isFinal) { recognizer.stop(); sendToClara(result[0].transcript); }
    };
    recognizer.onerror = () => micLabel("Didn't catch that. Tap to talk", false);
    recognizer.onend = () => { recognizer = null; micLabel("Tap to talk", false); };
    recognizer.start();
  }

  function stopVoice() {
    if (recognizer) recognizer.stop();
    if (window.speechSynthesis) window.speechSynthesis.cancel();
  }

  // Speak Clara's newest reply on a call. Reads the DOM only (never writes), debounced.
  let speakTimer = null;
  const speakObserver = new MutationObserver(() => {
    if (channel !== "voice" || !window.speechSynthesis) return;
    clearTimeout(speakTimer);
    speakTimer = setTimeout(() => {
      const rows = document.querySelectorAll("#clara-chat .message-row");
      const last = rows[rows.length - 1];
      if (!last || !last.classList.contains("bot-row") || last.querySelector(".typing-dots")) return;
      const text = last.innerText.trim();
      if (!text || text === lastSpoken) return;
      lastSpoken = text;
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(new SpeechSynthesisUtterance(text));
    }, 700);
  });
  const watchChat = new MutationObserver(() => {
    const chat = $("#clara-chat");
    if (chat) { watchChat.disconnect(); speakObserver.observe(chat, { childList: true, subtree: true, characterData: true }); }
  });
  watchChat.observe(document.documentElement, { childList: true, subtree: true });

  document.addEventListener("click", (ev) => {
    const ch = ev.target.closest("[data-channel]");
    if (ch) { ev.preventDefault(); setChannel(ch.getAttribute("data-channel")); return; }
    if (ev.target.closest("[data-voice-mic]")) { ev.preventDefault(); listen(); return; }
    const t = ev.target.closest("[data-clara-prompt],[data-clara-open],[data-clara-close],[data-presenter-toggle],[data-demo-reset]");
    if (!t) return;
    if (t.hasAttribute("data-clara-prompt")) {
      ev.preventDefault();
      sendToClara(t.getAttribute("data-clara-prompt"));
    } else if (t.hasAttribute("data-clara-open")) {
      ev.preventDefault();
      openDrawer();
    } else if (t.hasAttribute("data-clara-close")) {
      ev.preventDefault();
      closeDrawer();
    } else if (t.hasAttribute("data-presenter-toggle")) {
      ev.preventDefault();
      const on = !document.body.classList.contains("presenter");
      setPresenter(on);
      if (on) openDrawer(false);
    } else if (t.hasAttribute("data-demo-reset")) {
      ev.preventDefault();
      const reset = $("#clara-reset");
      if (reset) reset.click();
    }
  });

  document.addEventListener("submit", (ev) => {
    const form = ev.target.closest("[data-clara-form]");
    if (!form) return;
    ev.preventDefault();
    const input = form.querySelector("input");
    const text = (input.value || "").trim();
    input.value = "";
    if (text) sendToClara(text);
    else openDrawer();
  });

  // Directory filters: every [data-dir-filter] control narrows the [data-dir-item] cards next to it.
  document.addEventListener("change", (ev) => {
    const form = ev.target.closest("[data-dir]");
    if (!form) return;
    const page = form.closest(".svh-page") || document;
    const active = [...form.querySelectorAll("[data-dir-filter]")].map((c) => [c.dataset.dirFilter, c.type === "checkbox" ? (c.checked ? "true" : "") : c.value]);
    let shown = 0;
    page.querySelectorAll("[data-dir-item]").forEach((card) => {
      const ok = active.every(([key, val]) => !val || (key === "languages" ? card.dataset.languages.split("|").includes(val) : card.dataset[key] === val));
      card.hidden = !ok;
      if (ok) shown += 1;
    });
    const count = form.querySelector("[data-dir-count]");
    if (count) count.textContent = `${shown} doctor${shown === 1 ? "" : "s"}`;
    const empty = page.querySelector("[data-dir-empty]");
    if (empty) empty.hidden = shown > 0;
  });

  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && document.body.classList.contains("clara-open")) closeDrawer();
  });
})();
