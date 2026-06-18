/* Shared store: read config persistence + simple app state.
 * Read config mirrors legado's web read config (getReadConfig/saveReadConfig)
 * so reading preferences survive across sessions on the server. */
(function () {
  "use strict";

  const DEFAULT_CONFIG = {
    fontSize: 18,
    lineHeight: 1.9,
    theme: "paper",     // paper | sepia | dark
    fontFamily: "serif",
    chapterGap: 1.1,
  };

  const store = {
    config: { ...DEFAULT_CONFIG },
    user: { name: "读者" },

    async loadConfig() {
      try {
        const raw = await window.LegadoAPI.getReadConfig();
        const parsed = typeof raw === "string" ? JSON.parse(raw) : raw;
        if (parsed && typeof parsed === "object")
          this.config = { ...DEFAULT_CONFIG, ...parsed };
      } catch (e) { /* empty store is fine */ }
      return this.config;
    },

    async saveConfig() {
      try {
        await window.LegadoAPI.saveReadConfig(this.config);
      } catch (e) { /* non-fatal */ }
    },

    themeVars(theme) {
      switch (theme) {
        case "sepia":
          return { bg: "#e8dcc0", text: "#3a3026", accent: "#7a5230" };
        case "dark":
          return { bg: "#1d2027", text: "#cdd3df", accent: "#3c9a84" };
        default:
          return { bg: "#fbf7ee", text: "#2b2823", accent: "#2f7d6b" };
      }
    },
  };

  window.Store = store;
})();
