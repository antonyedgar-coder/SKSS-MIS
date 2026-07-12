/**
 * Searchable combobox: type to filter options, select to set hidden ID field.
 * options: [{ id: string|number, label: string }]
 */
function initCombobox(inputEl, hiddenEl, options, config) {
  const cfg = Object.assign({ allowEmpty: true, emptyLabel: "All" }, config || {});
  const wrapper = document.createElement("div");
  wrapper.className = "combobox position-relative";
  inputEl.parentNode.insertBefore(wrapper, inputEl);
  wrapper.appendChild(inputEl);

  const menu = document.createElement("div");
  menu.className = "combobox-menu list-group shadow-sm";
  menu.style.display = "none";
  wrapper.appendChild(menu);

  if (hiddenEl.parentNode !== wrapper) {
    wrapper.appendChild(hiddenEl);
  }

  let activeIndex = -1;

  function normalizedOptions() {
    const list = options.slice();
    if (cfg.allowEmpty) {
      list.unshift({ id: "", label: cfg.emptyLabel });
    }
    return list;
  }

  function filterOptions(query) {
    const q = query.trim().toLowerCase();
    if (!q) {
      return normalizedOptions();
    }
    return normalizedOptions().filter(function (opt) {
      return opt.label.toLowerCase().includes(q);
    });
  }

  function findExactMatch(label) {
    const q = label.trim().toLowerCase();
    return normalizedOptions().find(function (opt) {
      return opt.label.toLowerCase() === q;
    });
  }

  function renderMenu(items) {
    menu.innerHTML = "";
    if (!items.length) {
      menu.style.display = "none";
      return;
    }
    items.forEach(function (opt, idx) {
      const item = document.createElement("button");
      item.type = "button";
      item.className = "list-group-item list-group-item-action combobox-item";
      item.textContent = opt.label;
      item.dataset.index = String(idx);
      item.addEventListener("mousedown", function (e) {
        e.preventDefault();
        selectOption(opt);
      });
      menu.appendChild(item);
    });
    menu.style.display = "block";
    activeIndex = -1;
  }

  function selectOption(opt) {
    inputEl.value = opt.id === "" ? "" : opt.label;
    hiddenEl.value = opt.id === "" ? "" : String(opt.id);
    menu.style.display = "none";
    activeIndex = -1;
  }

  function syncFromHidden() {
    if (!hiddenEl.value) {
      inputEl.value = "";
      return;
    }
    const match = normalizedOptions().find(function (opt) {
      return String(opt.id) === String(hiddenEl.value);
    });
    if (match) {
      inputEl.value = match.label;
    }
  }

  inputEl.addEventListener("focus", function () {
    renderMenu(filterOptions(inputEl.value));
  });

  inputEl.addEventListener("input", function () {
    hiddenEl.value = "";
    renderMenu(filterOptions(inputEl.value));
  });

  inputEl.addEventListener("blur", function () {
    setTimeout(function () {
      menu.style.display = "none";
      if (!hiddenEl.value && inputEl.value.trim()) {
        const match = findExactMatch(inputEl.value);
        if (match) {
          selectOption(match);
        } else {
          inputEl.value = "";
        }
      }
    }, 150);
  });

  inputEl.addEventListener("keydown", function (e) {
    const items = menu.querySelectorAll(".combobox-item");
    if (!items.length) {
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      activeIndex = Math.min(activeIndex + 1, items.length - 1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      activeIndex = Math.max(activeIndex - 1, 0);
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (activeIndex >= 0 && items[activeIndex]) {
        items[activeIndex].dispatchEvent(new MouseEvent("mousedown"));
      }
      return;
    } else if (e.key === "Escape") {
      menu.style.display = "none";
      return;
    } else {
      return;
    }
    items.forEach(function (el, idx) {
      el.classList.toggle("active", idx === activeIndex);
    });
    if (activeIndex >= 0 && items[activeIndex]) {
      items[activeIndex].scrollIntoView({ block: "nearest" });
    }
  });

  syncFromHidden();
}
