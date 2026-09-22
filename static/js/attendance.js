

// Helper function for Bootstrap toast messages
function createToast(message, isError = false) {
  window.AppCore.toast(message, isError ? "error" : "success");
}

document.addEventListener("DOMContentLoaded", () => {
  // Apply initial server-rendered state (for hall passes + timers) before polling kicks in
  const serverStateEl = document.getElementById('serverState');
  if (serverStateEl && serverStateEl.textContent) {
    try {
      const initialState = JSON.parse(serverStateEl.textContent);
      updateAttendanceUI(
        initialState.active,
        pickTimeToday(initialState),
        initialState.projected_pay,
        initialState.hall_pass,
        initialState.done
      );
    } catch (e) {
      console.error('Failed to parse initial attendance state', e);
    }
  }

  // Handle contextual productivity actions.
  document.querySelectorAll(".attendance-action-btn").forEach(button => {
    button.addEventListener("click", () => {
      const action = button.dataset.action;

      if (action === 'start_work') {
        const pin = prompt("Enter your PIN to Start Work:");
        if (!pin) return;
        performTap(action, pin);
        return;
      }

      if (action === 'break') {
        const buttonState = button.dataset.state || 'break';
        const state = getAttendanceState();
        const hallPass = state ? state.hall_pass : null;
        if (buttonState === 'leave' && hallPass && hallPass.status === 'approved') {
          checkOutHallPass(hallPass.id);
          return;
        }
        if (buttonState === 'return' && hallPass && hallPass.status === 'left') {
          checkInHallPass(hallPass.id);
          return;
        }
        if (buttonState === 'pending') {
          createToast("Your hall pass request is pending approval.", true);
          return;
        }
        openBreakChoiceModal();
        return;
      }
    });
  });
});

let attendanceStateCache = {};

function rememberAttendanceState(state) {
  attendanceStateCache = state || {};
}

function getAttendanceState() {
  return attendanceStateCache || {};
}

function performTap(action, pin, reason = null) {
  const tapButton = document.querySelector(`.attendance-action-btn[data-action='${action}']`);
  if (tapButton) tapButton.disabled = true;

  // Map old action names to new API values
  let apiAction = action;
  if (action === 'break') apiAction = 'stop_work';

  const payload = { action: apiAction, pin };
  if (reason) {
    payload.reason = reason;
  }

  window.AppCore.csrfFetch("/api/tap", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  })
    .then(r => {
      // If session expired, redirect to login
      if (r.status === 401) {
        window.location.href = '/student/login?session_expired=1';
        return null;
      }
      return r.json();
    })
    .then(data => {
      if (!data) return; // Session expired, already redirecting
      if (data.status === "ok") {
        const state = { active: data.active, duration: data.duration, duration_today: data.duration_today, projected_pay: data.projected_pay, hall_pass: data.hall_pass, done: data.done };
        rememberAttendanceState(state);
        updateAttendanceUI(state.active, pickTimeToday(state), state.projected_pay, state.hall_pass, state.done);
        let message = `${action === "start_work" ? "Start Work" : "Break"} successful`;
        createToast(message);
      } else {
        createToast("Request failed: " + (data.error || "Unknown error"), true);
      }
      // The UI update function will correctly set the button states.
    })
    .catch(err => {
      console.error("Tap error:", err);
      createToast("The request could not reach the server. Check your connection and try again.", true);
      if (tapButton) tapButton.disabled = false; // Re-enable on error
    });
}

// Poll the server every 10 seconds to refresh class-scoped PROD status.
setInterval(() => {
  fetch("/api/student-status")
    .then(r => {
      // If session expired, redirect to login
      if (r.status === 401) {
        window.location.href = '/student/login?session_expired=1';
        return null;
      }
      return r.json();
    })
    .then(data => {
      if (!data) return; // Session expired, already redirecting
      if (data.status === 'ok' && data.attendance_state) {
        const state = data.attendance_state;
        rememberAttendanceState(state);
        updateAttendanceUI(state.active, pickTimeToday(state), state.projected_pay, state.hall_pass, state.done);
      }
    })
    .catch(err => console.error("Status polling error:", err));

}, 10000);

// "Time Today" is the day-bounded worked figure. Prefer duration_today; fall
// back to duration only for older server payloads that omit it.
function pickTimeToday(state) {
  if (state && state.duration_today !== undefined && state.duration_today !== null) {
    return state.duration_today;
  }
  return state ? state.duration : 0;
}

function updateAttendanceUI(isActive, duration, projectedPay, hallPass = null, doneForDay = false) {
  const row = document.querySelector(".attendance-state-row");
  if (!row) return;

  const statusCell = row.querySelector(".attendance-status");
  const durationCell = row.querySelector(".attendance-duration");
  const payCell = row.querySelector(".attendance-pay");
  const startWorkBtn = row.querySelector("#startWork");
  const breakWorkBtn = row.querySelector("#breakWork");

  rememberAttendanceState({ active: isActive, duration, projected_pay: projectedPay, hall_pass: hallPass, done: doneForDay });

  // Done-for-day is a terminal state for the class-local day (server already
  // refuses a same-day restart) -- it must read distinctly from a plain
  // in-between "Inactive" (e.g. mid-break) so a student doesn't try Start
  // Work expecting it to work.
  statusCell.textContent = doneForDay ? "Done for Day" : (isActive ? "Active" : "Inactive");
  statusCell.classList.toggle("attendance-status-active", isActive && !doneForDay);
  statusCell.classList.toggle("attendance-status-neutral", !isActive || doneForDay);
  statusCell.classList.toggle("fw-bold", isActive && !doneForDay);

  durationCell.textContent = formatDuration(duration);
  if (payCell) {
    payCell.textContent = Number(projectedPay || 0).toFixed(2);
  }

  // "Start Work" must also be disabled while out on an open hall pass, not
  // only while genuinely active. isActive is false in both cases, but only one
  // of them should offer a fresh clock-in -- the other should offer "Return".
  const onOpenHallPass = !!(hallPass && hallPass.status === 'left');
  if (startWorkBtn) startWorkBtn.disabled = isActive || onOpenHallPass || doneForDay;
  configureBreakButton(breakWorkBtn, isActive, hallPass, doneForDay);

  // Handle hall pass overlay
  updateHallPassOverlay(hallPass);
}

function configureBreakButton(button, isActive, hallPass, doneForDay = false) {
  if (!button) return;
  button.classList.remove('btn-warning', 'btn-danger', 'btn-primary', 'btn-outline-warning');

  // Terminal for the day -- takes priority over hall-pass/active state, which
  // shouldn't be reachable once done_for_day is recorded anyway, but this
  // keeps the button correct even if a stale hall-pass state lingers.
  if (doneForDay) {
    button.disabled = true;
    button.dataset.state = 'done';
    button.innerHTML = '<span class="material-symbols-outlined align-bottom me-1" aria-hidden="true">event_available</span> Done for Day';
    return;
  }

  // A hall pass the student has not yet returned from determines the primary
  // action REGARDLESS of isActive. "left" means the seat's latest attendance
  // event is inactive/hall_pass -- the student is out of the room -- and
  // isActive is therefore false, exactly like an ordinary break. Checking
  // hallPass BEFORE the isActive branch below is what previously let a
  // genuinely open pass fall through unrecognised: with isActive false, this
  // function returned a disabled, generically-labelled "Break" button before
  // ever inspecting hallPass, leaving "Start Work" as the only enabled control
  // while the student was still physically out of the room. Reproduced live
  // on 2026-09-21: the resulting click wrote a plain new work session on top
  // of the open pass and desynchronized the hall-pass log from the truth.
  if (hallPass && hallPass.status === 'left') {
    button.disabled = false;
    button.dataset.state = 'return';
    button.classList.add('btn-primary');
    button.innerHTML = '<span class="material-symbols-outlined align-bottom me-1" aria-hidden="true">login</span> Return';
    return;
  }

  button.disabled = !isActive;

  if (!isActive) {
    button.dataset.state = 'break';
    button.classList.add('btn-warning');
    button.innerHTML = '<span class="material-symbols-outlined align-bottom me-1" aria-hidden="true">pause_circle</span> Break';
    return;
  }

  if (hallPass && hallPass.status === 'approved') {
    button.dataset.state = 'leave';
    button.classList.add('btn-danger');
    button.innerHTML = '<span class="material-symbols-outlined align-bottom me-1" aria-hidden="true">logout</span> Leave';
    return;
  }

  if (hallPass && hallPass.status === 'left') {
    button.dataset.state = 'return';
    button.classList.add('btn-primary');
    button.innerHTML = '<span class="material-symbols-outlined align-bottom me-1" aria-hidden="true">login</span> Return';
    return;
  }

  if (hallPass && hallPass.status === 'pending') {
    button.dataset.state = 'pending';
    button.classList.add('btn-outline-warning');
    button.innerHTML = '<span class="material-symbols-outlined align-bottom me-1" aria-hidden="true">hourglass_top</span> Pending';
    return;
  }

  button.dataset.state = 'break';
  button.classList.add('btn-warning');
  button.innerHTML = '<span class="material-symbols-outlined align-bottom me-1" aria-hidden="true">pause_circle</span> Break';
}

function openBreakChoiceModal() {
  renderBreakDestinations([]);

  const modalEl = document.getElementById('breakChoiceModal');
  if (modalEl && window.bootstrap) {
    bootstrap.Modal.getOrCreateInstance(modalEl).show();
  }

  fetch('/api/hall-pass/available-types')
    .then(r => r.json())
    .then(data => {
      if (data.status === 'success') {
        // The endpoint returns pass_type_payload; this read `data.pass_types`,
        // which the API has never sent, so the destination list rendered empty.
        renderBreakDestinations(data.pass_type_payload || []);
      } else {
        renderBreakDestinationError(data.message || 'Unable to load hall-pass destinations.');
      }
    })
    .catch(err => {
      console.error('Hall pass destination load error:', err);
      renderBreakDestinationError('Unable to load hall-pass destinations.');
    });
}

function closeBreakChoiceModal() {
  const modalEl = document.getElementById('breakChoiceModal');
  if (modalEl && window.bootstrap) {
    bootstrap.Modal.getOrCreateInstance(modalEl).hide();
  }
}

function renderBreakDestinations(passTypes) {
  const list = document.getElementById('hallPassDestinationList');
  if (!list) return;
  list.textContent = '';

  if (!Array.isArray(passTypes) || passTypes.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'text-muted small';
    empty.textContent = 'No hall-pass destinations are currently available.';
    list.appendChild(empty);
    return;
  }

  passTypes.forEach(passType => {
    const destination = (passType && (passType.name || passType.pass_name))
      ? String(passType.name || passType.pass_name)
      : '';
    if (!destination) return;
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'btn btn-outline-primary text-start';
    button.textContent = destination;
    button.addEventListener('click', () => {
      requestHallPass(destination);
      closeBreakChoiceModal();
    });
    list.appendChild(button);
  });
}

function renderBreakDestinationError(message) {
  const list = document.getElementById('hallPassDestinationList');
  if (!list) return;
  list.textContent = '';
  list.appendChild(window.AppCore.buildAlertCard({
    level: 'danger',
    icon: 'error',
    title: 'Destinations unavailable',
    body: message,
    role: 'alert',
    className: 'mb-0',
  }));
}

document.addEventListener('DOMContentLoaded', () => {
  const doneBtn = document.getElementById('doneForDayBreakBtn');
  if (!doneBtn) return;
  doneBtn.addEventListener('click', () => {
    const pin = prompt("Enter your PIN to mark done for the day:");
    if (!pin) return;
    closeBreakChoiceModal();
    performTap('break', pin, "Done for the day");
  });
});

function updateHallPassOverlay(hallPass) {
  const passInfoDisplay = document.getElementById('hallPassInfo');

  if (!hallPass || hallPass.status === 'returned') {
    // No active hall pass - hide pass info
    if (passInfoDisplay) passInfoDisplay.hidden = true;
    return;
  }

  // Show pass info inline based on status
  if (passInfoDisplay) {
    passInfoDisplay.hidden = false;
    passInfoDisplay.textContent = ''; // Clear existing content

    const buildDetail = (text) => {
      const small = document.createElement('p');
      small.className = 'small mb-0';
      small.textContent = text;
      return small;
    };

    const showStatusCard = (level, icon, title, bodyParts) => {
      passInfoDisplay.appendChild(window.AppCore.buildAlertCard({
        level,
        icon,
        title,
        bodyNodes: bodyParts,
        className: 'mb-2',
      }));
    };

    if (hallPass.status === 'pending') {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'btn btn-sm btn-danger mt-2';
      button.textContent = 'Cancel';
      button.onclick = function () { cancelHallPass(hallPass.id); };

      showStatusCard('warning', 'hourglass_top', 'Hall pass pending approval', [
        buildDetail('Destination: ' + (hallPass.reason || 'N/A')),
        button,
      ]);
    } else if (hallPass.status === 'approved') {
      showStatusCard('success', 'check_circle', 'Hall pass approved', [
        buildDetail('Destination: ' + (hallPass.reason || 'N/A')),
      ]);
    } else if (hallPass.status === 'left') {
      showStatusCard('info', 'directions_walk', 'Currently out', [
        buildDetail('Destination: ' + (hallPass.reason || 'N/A')),
      ]);
    } else if (hallPass.status === 'rejected') {
      showStatusCard('danger', 'cancel', 'Hall pass denied', [
        buildDetail('Reason: ' + (hallPass.reason || 'N/A')),
      ]);
    } else {
      passInfoDisplay.hidden = true;
    }
  }
}

function refreshUi() {
  fetch("/api/student-status")
    .then(r => r.json())
    .then(statusData => {
      if (statusData.status === 'ok' && statusData.attendance_state) {
        const state = statusData.attendance_state;
        rememberAttendanceState(state);
        updateAttendanceUI(state.active, pickTimeToday(state), state.projected_pay, state.hall_pass, state.done);
      }
    });
}

function cancelHallPass(passId) {
  if (!confirm('Are you sure you want to cancel this hall pass request?')) {
    return;
  }

  window.AppCore.csrfFetch(`/api/hall-pass/request/${passId}/cancel`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' }
  })
    .then(r => r.json())
    .then(data => {
      if (data.status === 'success') {
        createToast('Hall pass request cancelled.');
        refreshUi();
      } else {
        createToast(data.message || 'Failed to cancel request.', true);
      }
    })
    .catch(err => {
      console.error('Cancel error:', err);
      createToast('Network error. Try again.', true);
    });
}

function requestHallPass(destination) {
  if (!destination || !destination.trim()) {
    return;
  }

  // FEAT-IDEN-002 "Credential boundary": hall-pass use takes the PIN. Prompted
  // the same way as "done for the day", which is the neighbouring break action.
  const pin = prompt(`Enter your PIN to request a hall pass to ${destination.trim()}:`);
  if (!pin) return;

  window.AppCore.csrfFetch('/api/hall-pass/request', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ destination: destination.trim(), pin: pin })
  })
    .then(r => r.json())
    .then(data => {
      if (data.status === 'success') {
        createToast('Hall pass request sent.');
        refreshUi();
      } else {
        createToast(data.message || 'Failed to request hall pass.', true);
      }
    })
    .catch(err => {
      console.error('Hall pass request error:', err);
      createToast('Network error. Try again.', true);
    });
}

function checkOutHallPass(passId) {
  if (!confirm('Ready to check out? This will mark you as leaving the classroom.')) {
    return;
  }

  window.AppCore.csrfFetch('/api/hall-pass/checkout', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pass_id: passId })
  })
    .then(r => r.json())
    .then(data => {
      if (data.status === 'success') {
        createToast(`Checked out for ${data.destination}. Have a safe trip!`);
        refreshUi();
      } else {
        createToast(data.message || 'Failed to check out.', true);
      }
    })
    .catch(err => {
      console.error('Checkout error:', err);
      createToast('Network error. Try again.', true);
    });
}

function checkInHallPass(passId) {
  if (!confirm('Ready to check in? This will mark you as returned to class.')) {
    return;
  }

  window.AppCore.csrfFetch('/api/hall-pass/checkin', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pass_id: passId })
  })
    .then(r => r.json())
    .then(data => {
      if (data.status === 'success') {
        createToast('Welcome back! You have been checked in.');
        refreshUi();
      } else {
        createToast(data.message || 'Failed to check in.', true);
      }
    })
    .catch(err => {
      console.error('Checkin error:', err);
      createToast('Network error. Try again.', true);
    });
}

// Removed acknowledgeApproval - no longer needed with inline display

function formatDuration(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return `${h}h ${m}m ${s}s`;
}
