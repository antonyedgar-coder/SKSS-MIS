document.addEventListener("DOMContentLoaded", function () {
  function toggleBankFields(select) {
    const form = select.closest("form");
    if (!form) return;
    const bankField = form.querySelector(".bank-field");
    if (!bankField) return;
    if (select.value === "bank") {
      bankField.classList.remove("d-none");
    } else {
      bankField.classList.add("d-none");
    }
  }

  document.querySelectorAll(".payment-mode").forEach(function (select) {
    toggleBankFields(select);
    select.addEventListener("change", function () {
      toggleBankFields(select);
    });
  });

  const today = new Date().toISOString().split("T")[0];
  document.querySelectorAll('input[type="date"]:not([value])').forEach(function (input) {
    if (!input.value) {
      input.value = today;
    }
  });

  const sidebar = document.getElementById("sidebar");
  const sidebarOpen = document.getElementById("sidebarOpen");
  const sidebarClose = document.getElementById("sidebarClose");
  const sidebarOverlay = document.getElementById("sidebarOverlay");

  function openSidebar() {
    if (sidebar) sidebar.classList.add("open");
    if (sidebarOverlay) sidebarOverlay.classList.add("show");
  }

  function closeSidebar() {
    if (sidebar) sidebar.classList.remove("open");
    if (sidebarOverlay) sidebarOverlay.classList.remove("show");
  }

  if (sidebarOpen) sidebarOpen.addEventListener("click", openSidebar);
  if (sidebarClose) sidebarClose.addEventListener("click", closeSidebar);
  if (sidebarOverlay) sidebarOverlay.addEventListener("click", closeSidebar);

  const currentPath = window.location.pathname;
  const dashboardLink = document.getElementById("navDashboardLink");
  if (dashboardLink && (currentPath === "/" || currentPath === "")) {
    dashboardLink.classList.add("active");
  }

  document.querySelectorAll(".sidebar-link").forEach(function (link) {
    const href = link.getAttribute("href");
    if (href && href !== "/" && currentPath.startsWith(href)) {
      link.classList.add("active");
    }
    if (href === currentPath) {
      link.classList.add("active");
    }
  });

  const settingsLink = document.getElementById("navSettingsLink");
  if (settingsLink && currentPath.startsWith("/masters") && currentPath !== "/masters/delete-test-data" && currentPath !== "/masters/activity-log") {
    settingsLink.classList.add("active");
  }

  const activityLogLink = document.getElementById("navActivityLogLink");
  if (activityLogLink && currentPath.startsWith("/masters/activity-log")) {
    activityLogLink.classList.add("active");
  }

  const activeLink = document.querySelector(".sidebar-link.active");
  if (activeLink) {
    const submenu = activeLink.closest(".sidebar-submenu");
    if (submenu) {
      submenu.classList.add("show");
      const section = submenu.closest(".sidebar-section");
      if (section) {
        const toggle = section.querySelector(".sidebar-group-toggle");
        if (toggle) {
          toggle.classList.remove("collapsed");
          toggle.setAttribute("aria-expanded", "true");
        }
      }
    }
  }
});
