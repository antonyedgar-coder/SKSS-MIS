/**
 * Single-input date range picker (Flatpickr range mode).
 * Keeps hidden from/to fields in YYYY-MM-DD for form submission.
 */
function initDateRangePicker(displayInput, fromInput, toInput, config) {
  if (typeof flatpickr === "undefined") {
    return;
  }

  var cfg = Object.assign(
    {
      placeholder: "Select from date to to date",
      dateFormat: "d-M-Y",
      allowInput: false,
    },
    config || {}
  );

  var defaultDates = [];
  if (fromInput.value) {
    defaultDates.push(fromInput.value);
  }
  if (toInput.value) {
    defaultDates.push(toInput.value);
  }

  function syncHidden(selectedDates) {
    if (!selectedDates.length) {
      fromInput.value = "";
      toInput.value = "";
      return;
    }
    fromInput.value = flatpickr.formatDate(selectedDates[0], "Y-m-d");
    if (selectedDates.length > 1) {
      toInput.value = flatpickr.formatDate(selectedDates[1], "Y-m-d");
    } else {
      toInput.value = "";
    }
  }

  var picker = flatpickr(displayInput, {
    mode: "range",
    dateFormat: cfg.dateFormat,
    allowInput: cfg.allowInput,
    defaultDate: defaultDates.length ? defaultDates : null,
    locale: { rangeSeparator: " to " },
    onChange: function (selectedDates) {
      syncHidden(selectedDates);
    },
    onClose: function (selectedDates) {
      syncHidden(selectedDates);
    },
  });

  if (defaultDates.length === 2) {
    displayInput.placeholder = cfg.placeholder;
  } else {
    displayInput.placeholder = cfg.placeholder;
  }

  return picker;
}

function bindDateRangeFormValidation(form, displayInput, fromInput, toInput) {
  form.addEventListener("submit", function (e) {
    if (!fromInput.value || !toInput.value) {
      e.preventDefault();
      displayInput.classList.add("is-invalid");
      displayInput.focus();
      return false;
    }
    displayInput.classList.remove("is-invalid");
    return true;
  });
}
