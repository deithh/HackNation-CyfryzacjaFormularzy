document.addEventListener("DOMContentLoaded", () => {
  const tabButtons = Array.from(document.querySelectorAll(".tab-btn"));
  const tabPanels = Array.from(document.querySelectorAll(".tab-panel"));

  function activateTab(index) {
    tabButtons.forEach((btn, idx) => {
      const active = idx === index;
      btn.classList.toggle("active", active);
      btn.setAttribute("aria-selected", active ? "true" : "false");
    });
    tabPanels.forEach((panel, idx) => {
      panel.classList.toggle("active", idx === index);
    });
  }

  tabButtons.forEach((btn, idx) => {
    btn.addEventListener("click", () => activateTab(idx));
  });

  document.querySelectorAll(".js-next-tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      const nextIdx = Number(btn.dataset.nextIndex);
      if (!Number.isNaN(nextIdx)) activateTab(nextIdx);
    });
  });

  document.querySelectorAll(".js-prev-tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      const prevIdx = Number(btn.dataset.prevIndex);
      if (!Number.isNaN(prevIdx)) activateTab(prevIdx);
    });
  });

  // Podgląd prostych warunków SHOW opartych o wartość wybraną w polu źródłowym
  function evaluateConditions() {
    const valuesBySource = new Map();
    document.querySelectorAll(".js-trigger-field").forEach((el) => {
      const source = (el.dataset.sourceTech || "").trim();
      if (!source) return;
      const values = valuesBySource.get(source) || new Set();
      const addValue = (value) => { if (value) values.add(value.trim().toLowerCase()); };
      if (el.tagName === "SELECT" && el.value) {
        addValue(el.value);
        addValue(el.options[el.selectedIndex]?.dataset.tech);
      } else if (el.type === "radio" || el.type === "checkbox") {
        if (el.checked && el.value) {
          addValue(el.value);
          addValue(el.dataset.tech);
        }
      } else if (el.value) {
        addValue(el.value);
      }
      valuesBySource.set(source, values);
    });

    document.querySelectorAll(".conditional-field").forEach((item) => {
      let conditions = [];
      try {
        conditions = JSON.parse(item.dataset.showConditions || "[]");
      } catch (_) {
        conditions = [];
      }

      if (!conditions.length) {
        item.style.display = "none";
        return;
      }
      const matched = conditions.every((condition) =>
        valuesBySource.get(String(condition.sourceTechName || ""))?.has(
          String(condition.value || "").trim().toLowerCase()
        )
      );
      item.style.display = matched ? "" : "none";
    });

    const sections = Array.from(document.querySelectorAll(".section-box")).reverse();
    sections.forEach((section) => {
      const item = section.closest(".form-item");
      if (!item) return;
      const children = Array.from(
        section.querySelectorAll(":scope > .section-fields > .form-item, :scope .repeating-entry:first-child > .entry-fields > .form-item")
      );
      const hasVisible = children.some(
        (child) => child.style.display !== "none" && !child.classList.contains("section-empty")
      );
      item.classList.toggle("section-empty", !hasVisible);
    });
  }

  document.querySelectorAll(".js-trigger-field").forEach((el) => {
    el.addEventListener("change", evaluateConditions);
    el.addEventListener("input", evaluateConditions);
  });
  evaluateConditions();

  // Obsługa sekcji powtarzających się w trybie podglądu
  document.querySelectorAll(".repeating-section").forEach((section) => {
    const container = section.querySelector("[data-repeating-container]");
    const addBtn = section.querySelector(".btn-add-entry");
    if (!container || !addBtn) return;

    function refreshEntryHeaders() {
      const entries = Array.from(container.querySelectorAll(".repeating-entry"));
      entries.forEach((entry, idx) => {
        const titleEl = entry.querySelector(".entry-header span");
        if (titleEl) titleEl.textContent = `Wpis #${idx + 1}`;
        const removeBtn = entry.querySelector(".btn-remove-entry");
        if (removeBtn) removeBtn.disabled = entries.length <= 1;
      });
    }

    container.addEventListener("click", (event) => {
      const removeBtn = event.target.closest(".btn-remove-entry");
      if (!removeBtn) return;
      const entry = removeBtn.closest(".repeating-entry");
      const entries = container.querySelectorAll(".repeating-entry");
      if (entry && entries.length > 1) {
        entry.remove();
        refreshEntryHeaders();
      }
    });

    addBtn.addEventListener("click", () => {
      const firstEntry = container.querySelector(".repeating-entry");
      if (!firstEntry) return;
      const clone = firstEntry.cloneNode(true);
      clone.querySelectorAll("input, select, textarea").forEach((inp) => {
        if (inp.type === "checkbox" || inp.type === "radio") {
          inp.checked = false;
        } else if (inp.type !== "file") {
          inp.value = "";
        }
      });
      container.appendChild(clone);
      refreshEntryHeaders();
    });

    refreshEntryHeaders();
  });
});
