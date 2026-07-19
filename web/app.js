const state = {
  tab: "focus",
  token: localStorage.getItem("focus_api_token") || "",
  data: null,
  meta: null,
  clock: null,
  seenNotifications: new Set(),
  companionMessages: [],
  companionBusy: false,
};

const app = document.querySelector("#app");
const modal = document.querySelector("#modal");
const modalForm = document.querySelector("#modalForm");
const toast = document.querySelector("#toast");

class AuthError extends Error {}

const esc = (value = "") => String(value).replace(/[&<>'"]/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[char]));
const fmtMinutes = seconds => t("{{count}} min", {count: Math.round(Number(seconds || 0) / 60)});
const fmtClock = seconds => {
  const value = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(value / 3600);
  const minutes = Math.floor((value % 3600) / 60);
  const secs = value % 60;
  return hours ? `${hours}:${String(minutes).padStart(2,"0")}:${String(secs).padStart(2,"0")}` : `${String(minutes).padStart(2,"0")}:${String(secs).padStart(2,"0")}`;
};

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 2200);
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (state.token) headers.set("X-Focus-Token", state.token);
  if (options.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const response = await fetch(path, {...options, headers});
  if (response.status === 401) {
    throw new AuthError(t("Focus needs the API token generated during installation."));
  }
  const result = await response.json().catch(() => ({detail: response.statusText}));
  if (!response.ok) throw new Error(result.detail || t("Focus request failed"));
  return result;
}

async function refresh({quiet = false} = {}) {
  try {
    const result = await api("/api/bootstrap");
    state.data = result.data;
    render();
    handleNotifications(result.data.notifications || []);
  } catch (error) {
    if (!quiet) app.innerHTML = error instanceof AuthError ? renderTokenGate() : `<section class="card error-card"><h2>${t("Focus could not load")}</h2><p>${esc(error.message)}</p><button class="primary" data-action="retry">${t("Try again")}</button></section>`;
  }
}

function renderTokenGate() {
  return `<section class="card error-card"><div class="eyebrow">${t("Private by default")}</div><h2>${t("Connect this browser")}</h2><p>${t("Paste the API token created by the installer. It stays only in this browser.")}</p><form id="tokenGate" class="token-form"><input name="token" type="password" autocomplete="off" required placeholder="${t("Focus API token")}"><button class="primary">${t("Connect")}</button></form></section>`;
}

function activeSeconds(session) {
  if (!session) return 0;
  const base = Number(session.elapsed_seconds || 0);
  const updated = state.clock?.sessionId === session.id ? state.clock.seconds : base;
  return Math.max(base, updated);
}

function timerValue(session) {
  const elapsed = activeSeconds(session);
  if (session.mode === "countup" || !session.planned_minutes) return fmtClock(elapsed);
  return fmtClock(Number(session.planned_minutes) * 60 - elapsed);
}

function syncClock() {
  const session = state.data?.active_session;
  if (!session) {
    state.clock = null;
    return;
  }
  if (!state.clock || state.clock.sessionId !== session.id) state.clock = {sessionId: session.id, seconds: Number(session.elapsed_seconds || 0)};
}

function projectName(projectId) {
  return state.data.projects.find(item => item.id === projectId)?.title || t("No project");
}

function directionName(directionId) {
  return state.data.directions.find(item => item.id === directionId)?.title || t("Independent");
}

function renderTimer() {
  const session = state.data.active_session;
  const policyApps = state.data.policy.blocked_apps || [];
  if (!session) return `
    <section class="card timer-card idle">
      <div class="eyebrow">${t("Ready when you are")}</div>
      <h2 class="timer-title">${t("Start with one clear task.")}</h2>
      <p class="timer-goal">${t("Choose something from today, or create a free-focus session.")}</p>
      <div class="timer-value">25:00</div>
      <div class="timer-state">${t("No active session")}</div>
      <div class="timer-actions"><button class="primary" data-action="free-focus">${t("Start free focus")}</button></div>
      <div class="monitor-note"><span class="dot"></span>${esc(policyApps.join(", ") || t("Distraction monitoring is off"))}</div>
    </section>`;
  const task = state.data.tasks.find(item => item.id === session.task_id);
  const label = task?.title || session.goal || session.title || t("Free focus");
  return `
    <section class="card timer-card">
      <div class="eyebrow">${session.status === "paused" ? t("Paused") : t("Focusing")}</div>
      <h2 class="timer-title">${esc(label)}</h2>
      <p class="timer-goal">${esc(task?.details || projectName(session.project_id))}</p>
      <div class="timer-value" id="timerValue">${timerValue(session)}</div>
      <div class="timer-state">${session.status === "paused" ? t("Take a breath, then decide.") : focusValueLabel(session.mode)}</div>
      <div class="timer-actions">
        <button class="primary" data-session-action="${session.status === "paused" ? "resume" : "pause"}">${session.status === "paused" ? t("Resume") : t("Pause")}</button>
        <button class="secondary" data-session-action="complete">${t("End session")}</button>
      </div>
      <div class="monitor-note"><span class="dot"></span>${esc(policyApps.join(", ") || t("No apps monitored"))} · ${t("one strike per distinct open")}</div>
    </section>`;
}

function renderTaskRow(task) {
  return `<div class="task-row">
    <button class="task-check" data-complete-task="${task.id}" aria-label="${esc(t("Complete {{title}}", {title: task.title}))}"></button>
    <div class="task-copy"><strong>${esc(task.title)}</strong><span>${esc(projectName(task.project_id))} · ${t("{{count}} min", {count: task.estimated_minutes})}${task.details ? ` · ${esc(task.details)}` : ""}</span></div>
    <div class="task-tools"><button data-start-task="${task.id}">${t("Start")}</button><button data-edit-task="${task.id}">•••</button></div>
  </div>`;
}

function renderFocus() {
  const now = new Date();
  const localToday = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,"0")}-${String(now.getDate()).padStart(2,"0")}`;
  const open = state.data.tasks.filter(item => ["todo","doing"].includes(item.status) && (!item.target_date || item.target_date <= localToday));
  const stats = state.data.stats.today;
  const done = stats.completed_tasks;
  const total = open.length + done;
  return `<div class="focus-grid">
    ${renderTimer()}
    <section class="card task-card">
      <div class="section-head"><div><div class="eyebrow">${t("Today")}</div><h2>${t("Your focus list")}</h2></div><button class="ghost" data-action="new-task">${t("Add")}</button></div>
      <div class="summary-grid">
        <div class="summary-item"><strong>${stats.focus_minutes}</strong><span>${t("minutes")}</span></div>
        <div class="summary-item"><strong>${stats.completed_tasks}</strong><span>${t("completed")}</span></div>
        <div class="summary-item"><strong>${stats.session_count}</strong><span>${t("sessions")}</span></div>
        <div class="summary-item"><strong>${stats.interruptions}</strong><span>${t("interruptions")}</span></div>
      </div>
      <div class="progress"><span style="width:${total ? Math.round(done / total * 100) : 0}%"></span></div>
      <div class="task-list">${open.length ? open.map(renderTaskRow).join("") : `<div class="empty">${t("Nothing pending. Make space for rest.")}</div>`}</div>
    </section>
  </div>`;
}

function renderProjects() {
  const directions = state.data.directions.filter(item => item.status !== "archived").map(direction => {
    const count = state.data.projects.filter(project => project.direction_id === direction.id && project.status !== "archived").length;
    return `<div class="direction-item"><div><span>${t("Direction")}</span><strong>${esc(direction.title)}</strong><p>${esc(direction.goal || t("A longer-term area worth moving forward."))}</p></div><b>${t(count === 1 ? "{{count}} project" : "{{count}} projects", {count})}</b></div>`;
  }).join("");
  const cards = state.data.projects.filter(item => item.status !== "archived").map(project => {
    const tasks = state.data.tasks.filter(task => task.project_id === project.id);
    const done = tasks.filter(task => task.status === "done").length;
    const percent = tasks.length ? Math.round(done / tasks.length * 100) : 0;
    return `<section class="card page-card project-card">
      <div class="eyebrow">${esc(directionName(project.direction_id))} · ${esc(focusValueLabel(project.status))}</div><h2>${esc(project.title)}</h2>
      <p class="project-meta">${esc(project.outcome || t("Define what done looks like."))}</p>
      <div class="progress"><span style="width:${percent}%"></span></div>
      <div class="project-footer"><span>${t("{{done}} / {{total}} tasks", {done, total: tasks.length})}</span><button class="ghost" data-action="new-task" data-project="${project.id}">${t("Add task")}</button></div>
    </section>`;
  }).join("");
  return `<div class="section-head"><div><div class="eyebrow">${t("Structure")}</div><h2>${t("Directions and projects")}</h2></div><div class="top-actions"><button class="secondary" data-action="new-direction">${t("New direction")}</button><button class="primary" data-action="new-project">${t("＋ New project")}</button></div></div>
    <div class="direction-strip">${directions || `<div class="direction-item"><div><span>${t("Direction")}</span><strong>${t("Choose a longer-term direction")}</strong><p>${t("Projects can live inside it, while one-off projects stay independent.")}</p></div></div>`}</div>
    <div class="page-grid">${cards || `<section class="card empty">${t("Create your first project.")}</section>`}</div>`;
}

function renderStats() {
  const today = state.data.stats.today;
  const week = state.data.stats.week;
  const grouped = week.by_activity || [];
  return `<div class="page-grid">
    <section class="card page-card stat-hero">
      <div class="stat-block"><strong>${today.focus_minutes}</strong><span>${t("focused minutes today")}</span></div>
      <div class="stat-block"><strong>${today.session_count}</strong><span>${t("sessions today")}</span></div>
      <div class="stat-block"><strong>${week.focus_minutes}</strong><span>${t("minutes this week")}</span></div>
    </section>
    <section class="card page-card"><div class="section-head"><div><div class="eyebrow">${t("This week")}</div><h2>${t("By activity")}</h2></div></div>
      <div class="task-list">${grouped.map(row => `<div class="task-row"><div></div><div class="task-copy"><strong>${esc(row.title)}</strong><span>${fmtMinutes(row.focus_seconds)} · ${t(row.session_count === 1 ? "{{count}} session" : "{{count}} sessions", {count: row.session_count})}</span></div></div>`).join("") || `<div class="empty">${t("No sessions yet.")}</div>`}</div>
    </section>
    <section class="card page-card"><div class="section-head"><div><div class="eyebrow">${t("Distractions")}</div><h2>${t("Interventions")}</h2></div></div>
      <div class="task-list">${state.data.interventions.slice(0,10).map(row => `<div class="task-row"><div></div><div class="task-copy"><strong>${esc(row.app_name)} · ${t("Strike {{count}}", {count: row.strike_number})}</strong><span>${esc(focusValueLabel(row.status))} · ${fmtMinutes(row.duration_seconds)}</span></div></div>`).join("") || `<div class="empty">${t("No distraction events.")}</div>`}</div>
    </section>
  </div>`;
}

function renderSettings() {
  const policy = state.data.policy;
  const provider = state.meta?.ai_provider || "none";
  return `<div class="page-grid">
    <section class="card page-card"><div class="section-head"><div><div class="eyebrow">${t("Focus policy")}</div><h2>${t("Distraction rules")}</h2></div><button class="ghost" data-action="edit-policy">${t("Edit")}</button></div>
      <div class="settings-list">
        <div class="settings-row"><div><strong>${t("Monitored apps")}</strong><span>${t("One strike per distinct app opening")}</span></div><div class="chips">${policy.blocked_apps.map(app => `<span class="chip">${esc(app)}</span>`).join("") || `<span class="chip">${t("None")}</span>`}</div></div>
        <div class="settings-row"><div><strong>${t("Grace period")}</strong><span>${t("Ignore brief accidental opens")}</span></div><b>${policy.grace_seconds}s</b></div>
        <div class="settings-row"><div><strong>${t("Punishment threshold")}</strong><span>${t("Distinct openings within one session")}</span></div><b>${policy.strikes_for_punishment}</b></div>
      </div>
    </section>
    <section class="card page-card"><div class="section-head"><div><div class="eyebrow">${t("Connections")}</div><h2>${t("Optional integrations")}</h2></div></div>
      <div class="settings-list">
        <div class="settings-row"><div><strong>${t("AI companion")}</strong><span>${t("Configured during installation")}</span></div><b>${esc(focusValueLabel(provider))}</b></div>
        <div class="settings-row"><div><strong>Telegram</strong><span>${t("Optional delivery channel")}</span></div><b>${t(state.meta?.telegram_enabled ? "On" : "Off")}</b></div>
        <div class="settings-row"><div><strong>${t("Browser notifications")}</strong><span>${t("Timer and distraction reminders")}</span></div><button class="secondary" data-action="notifications">${t("Enable")}</button></div>
        <div class="settings-row"><div><strong>${t("API token")}</strong><span>${t("Stored only in this browser")}</span></div><button class="secondary" data-action="change-token">${t("Change")}</button></div>
        <div class="settings-row"><div><strong>${t("Language")}</strong><span>${t("Interface language on this browser")}</span></div><button class="secondary" data-action="switch-locale">${focusLocale === "zh-CN" ? t("English") : t("Simplified Chinese")}</button></div>
      </div>
    </section>
  </div>`;
}

function renderCompanion() {
  const enabled = Boolean(state.meta?.ai_enabled);
  const messages = state.companionMessages.map(item => `
    <div class="chat-message ${item.role}"><span>${item.role === "user" ? t("You") : "Focus"}</span><p>${esc(item.content).replace(/\n/g, "<br>")}</p></div>`).join("");
  return `<section class="card companion-card">
    <div class="section-head"><div><div class="eyebrow">${t("Optional · {{provider}}", {provider: esc(focusValueLabel(state.meta?.ai_provider || "none"))})}</div><h2>${t("Focus companion")}</h2></div><span class="chip">${enabled ? esc(state.meta.ai_model) : t("Off")}</span></div>
    ${enabled ? `<div class="chat-thread" id="chatThread">${messages || `<div class="companion-empty"><strong>${t("What should we focus on?")}</strong><p>${t("I can read your current plan, create or rearrange tasks, and start the timer.")}</p></div>`}</div>
      <form class="chat-form" id="companionForm"><textarea name="message" rows="2" required placeholder="${t("Plan my next hour…")}" ${state.companionBusy ? "disabled" : ""}></textarea><button class="primary" ${state.companionBusy ? "disabled" : ""}>${state.companionBusy ? t("Thinking…") : t("Send")}</button></form>`
      : `<div class="companion-empty"><strong>${t("No model is connected.")}</strong><p>${t("Focus works without AI. To add one, set the provider, model, and API key in <code>.env</code>, then restart Focus.")}</p></div>`}
  </section>`;
}

function render() {
  if (!state.data) return;
  syncClock();
  app.innerHTML = state.tab === "focus" ? renderFocus() : state.tab === "projects" ? renderProjects() : state.tab === "companion" ? renderCompanion() : state.tab === "stats" ? renderStats() : renderSettings();
  if (state.tab === "companion") requestAnimationFrame(() => { const thread = document.querySelector("#chatThread"); if (thread) thread.scrollTop = thread.scrollHeight; });
}

function field(label, name, value = "", type = "text", extra = "") {
  return `<label class="field"><span>${esc(label)}</span><input name="${esc(name)}" value="${esc(value)}" type="${type}" ${extra}></label>`;
}

function selectField(label, name, options, selected) {
  return `<label class="field"><span>${esc(label)}</span><select name="${esc(name)}">${options.map(([value, text]) => `<option value="${esc(value)}" ${String(value) === String(selected) ? "selected" : ""}>${esc(text)}</option>`).join("")}</select></label>`;
}

function openModal({title, eyebrow = "Focus", body, submit = t("Save"), onSubmit}) {
  document.querySelector("#modalTitle").textContent = title;
  document.querySelector("#modalEyebrow").textContent = eyebrow;
  document.querySelector("#modalBody").innerHTML = body;
  document.querySelector("#modalSubmit").textContent = submit;
  modalForm.onsubmit = async event => {
    event.preventDefault();
    try {
      await onSubmit(Object.fromEntries(new FormData(modalForm).entries()));
      modal.close();
      await refresh();
    } catch (error) { showToast(error.message); }
  };
  modal.showModal();
}

function taskModal(task = null, defaultProject = null) {
  const projects = [["", t("No project")], ...state.data.projects.map(item => [item.id, item.title])];
  openModal({
    title: t(task ? "Edit task" : "New task"), eyebrow: t("Task"), submit: t(task ? "Save task" : "Create task"),
    body: `${field(t("Title"), "title", task?.title || "", "text", "required autofocus")}
      <label class="field"><span>${t("Details")}</span><textarea name="details" rows="3">${esc(task?.details || "")}</textarea></label>
      ${selectField(t("Project"), "project_id", projects, task?.project_id || defaultProject || "")}
      <div class="form-grid">${field(t("Minutes"), "estimated_minutes", task?.estimated_minutes || 25, "number", "min=1")}${selectField(t("Priority"), "priority", [[1,t("High")],[2,t("Important")],[3,t("Normal")],[4,t("Low")],[5,t("Someday")]], task?.priority || 3)}</div>
      ${field(t("Monitored apps"), "blocked_apps", (task?.blocked_apps || []).join(", "), "text", `placeholder="${esc(t("Leave blank to use global policy"))}"`)}
      ${task ? `<button type="button" class="danger" data-abandon-task="${task.id}">${t("Abandon task")}</button>` : ""}`,
    onSubmit: async form => {
      const payload = {
        project_id: form.project_id ? Number(form.project_id) : null, title: form.title.trim(), details: form.details.trim() || null,
        status: task?.status || "todo", task_scope: task?.task_scope || "daily", priority: Number(form.priority), sort_order: task?.sort_order || 0,
        estimated_minutes: Number(form.estimated_minutes || 25), target_date: task?.target_date || new Date().toISOString().slice(0,10),
        blocked_apps: form.blocked_apps.split(/[,，]/).map(item => item.trim()).filter(Boolean),
      };
      await api(task ? `/api/tasks/${task.id}` : "/api/tasks", {method: task ? "PUT" : "POST", body: JSON.stringify(payload)});
    },
  });
}

function projectModal() {
  const directions = [["", t("Independent project")], ...state.data.directions.map(item => [item.id, item.title])];
  openModal({title: t("New project"), eyebrow: t("Project"), submit: t("Create project"), body: `${field(t("Project name"), "title", "", "text", "required autofocus")}<label class="field"><span>${t("Desired outcome")}</span><textarea name="outcome" rows="3"></textarea></label>${selectField(t("Direction"), "direction_id", directions, "")}${field(t("Weekly target"), "weekly_target_minutes", 0, "number", "min=0")}`,
    onSubmit: form => api("/api/projects", {method:"POST", body:JSON.stringify({direction_id:form.direction_id?Number(form.direction_id):null,title:form.title.trim(),outcome:form.outcome.trim()||null,notes:null,status:"active",weekly_target_minutes:Number(form.weekly_target_minutes||0),target_minutes:0,due_date:null,sort_order:state.data.projects.length})})});
}

function directionModal() {
  openModal({title:t("New direction"),eyebrow:t("Long-term"),submit:t("Create direction"),body:`${field(t("Direction name"),"title","","text","required autofocus")}<label class="field"><span>${t("What should this direction change?")}</span><textarea name="goal" rows="3"></textarea></label>${field(t("Weekly target minutes"),"weekly_target_minutes",0,"number","min=0")}`,onSubmit:form=>api("/api/directions",{method:"POST",body:JSON.stringify({title:form.title.trim(),goal:form.goal.trim()||null,status:"active",weekly_target_minutes:Number(form.weekly_target_minutes||0),sort_order:state.data.directions.length})})});
}

function importPlanModal() {
  const projects = [["", t("No project")], ...state.data.projects.map(item => [item.id, item.title])];
  openModal({
    title:t("Import a GPT plan"), eyebrow:t("Markdown"), submit:t("Import tasks"),
    body:`<label class="field"><span>${t("Paste the plan")}</span><textarea name="markdown" rows="12" required autofocus placeholder="${t("1. Read the chapter | 25 min\n2. Make a comparison table | 35 min")}"></textarea></label>${selectField(t("Assign every task to"), "project_id", projects, "")}`,
    onSubmit:async form=>{
      const result = await api("/api/plans/import", {method:"POST", body:JSON.stringify({markdown:form.markdown,project_id:form.project_id?Number(form.project_id):null,target_date:null})});
      const breaks = result.data.breaks.length;
      showToast(t(breaks ? "Imported {{tasks}} tasks · recognized {{breaks}} break." : "Imported {{tasks}} tasks.", {tasks: result.data.tasks.length, breaks}));
    },
  });
}

function policyModal() {
  const policy = state.data.policy;
  openModal({title:t("Distraction rules"),eyebrow:t("Policy"),body:`${field(t("Monitored apps"), "blocked_apps", policy.blocked_apps.join(", "), "text", `placeholder="${t("Instagram, TikTok")}"`)}<div class="form-grid">${field(t("Grace seconds"),"grace_seconds",policy.grace_seconds,"number","min=15")}${field(t("Punishment after"),"strikes_for_punishment",policy.strikes_for_punishment,"number","min=1")}</div>${field(t("Reminder cooldown seconds"),"reminder_cooldown_seconds",policy.reminder_cooldown_seconds,"number","min=30")}<label class="field"><span>${t("Punishment pool · one per line")}</span><textarea name="punishment_pool" rows="4">${esc(policy.punishment_pool.join("\n"))}</textarea></label>`,onSubmit:form=>api("/api/policy",{method:"PUT",body:JSON.stringify({blocked_apps:form.blocked_apps.split(/[,，]/).map(x=>x.trim()).filter(Boolean),grace_seconds:Number(form.grace_seconds),strikes_for_punishment:Number(form.strikes_for_punishment),reminder_cooldown_seconds:Number(form.reminder_cooldown_seconds),punishment_pool:form.punishment_pool.split("\n").map(x=>x.trim()).filter(Boolean)})})});
}

function tokenModal() {
  openModal({title:t("Connect this browser"),eyebrow:t("Security"),submit:t("Save token"),body:field(t("Focus API token"),"token",state.token,"password","required autocomplete='off'"),onSubmit:async form=>{state.token=form.token.trim();localStorage.setItem("focus_api_token",state.token);}});
}

function freeFocusModal() {
  openModal({title:t("Start free focus"),eyebrow:t("Timer"),submit:t("Start"),body:`${field(t("Title"),"title",t("Free focus"),"text","required autofocus")}${field(t("Minutes"),"minutes",25,"number","min=1 max=1440")}`,onSubmit:form=>api("/api/sessions",{method:"POST",body:JSON.stringify({task_id:null,project_id:null,session_kind:"work",mode:"pomodoro",title:form.title.trim(),goal:null,planned_minutes:Number(form.minutes||25)})})});
}

async function enableNotifications() {
  if (!("Notification" in window)) return showToast(t("This browser does not support notifications."));
  const result = await Notification.requestPermission();
  showToast(t(result === "granted" ? "Browser notifications enabled." : "Notifications were not enabled."));
}

function handleNotifications(rows) {
  rows.forEach(row => {
    if (state.seenNotifications.has(row.id)) return;
    state.seenNotifications.add(row.id);
    showToast(row.body);
    if (Notification.permission === "granted") new Notification(row.title, {body: row.body, tag: `focus-${row.id}`});
  });
}

document.addEventListener("click", async event => {
  const tab = event.target.closest("[data-tab]");
  if (tab) {
    state.tab = tab.dataset.tab;
    document.querySelectorAll("[data-tab]").forEach(button => button.classList.toggle("active", button === tab));
    return render();
  }
  const action = event.target.closest("[data-action]")?.dataset.action;
  if (action === "new-task") return taskModal(null, event.target.closest("[data-project]")?.dataset.project || null);
  if (action === "new-project") return projectModal();
  if (action === "new-direction") return directionModal();
  if (action === "import-plan") return importPlanModal();
  if (action === "edit-policy") return policyModal();
  if (action === "notifications") return enableNotifications();
  if (action === "retry") return refresh();
  if (action === "change-token") return tokenModal();
  if (action === "free-focus") return freeFocusModal();
  if (action === "switch-locale") return toggleFocusLocale();
  const editId = event.target.closest("[data-edit-task]")?.dataset.editTask;
  if (editId) return taskModal(state.data.tasks.find(item => item.id === Number(editId)));
  const startId = event.target.closest("[data-start-task]")?.dataset.startTask;
  if (startId) {
    const task = state.data.tasks.find(item => item.id === Number(startId));
    await api("/api/sessions", {method:"POST",body:JSON.stringify({task_id:task.id,project_id:task.project_id,session_kind:"work",mode:"pomodoro",title:task.title,goal:task.details,planned_minutes:task.estimated_minutes})});
    return refresh();
  }
  const completeId = event.target.closest("[data-complete-task]")?.dataset.completeTask;
  if (completeId) {
    const result = await api(`/api/tasks/${completeId}/complete`, {method:"POST"});
    showToast(result.data.next_task ? t("Done. Next: {{title}}", {title: result.data.next_task.title}) : t("Done. Your list is clear."));
    return refresh();
  }
  const abandonId = event.target.closest("[data-abandon-task]")?.dataset.abandonTask;
  if (abandonId) { await api(`/api/tasks/${abandonId}/abandon`, {method:"POST"}); modal.close(); showToast(t("Task abandoned.")); return refresh(); }
  const sessionAction = event.target.closest("[data-session-action]")?.dataset.sessionAction;
  if (sessionAction && state.data.active_session) {
    await api(`/api/sessions/${state.data.active_session.id}`, {method:"PUT",body:JSON.stringify({action:sessionAction,note:null})});
    return refresh();
  }
});

document.addEventListener("submit", async event => {
  if (event.target.id === "companionForm") {
    event.preventDefault();
    const input = new FormData(event.target).get("message").trim();
    if (!input || state.companionBusy) return;
    state.companionMessages.push({role:"user", content:input});
    state.companionBusy = true;
    render();
    try {
      const result = await api("/api/companion/chat", {method:"POST", body:JSON.stringify({messages:state.companionMessages.slice(-30)})});
      state.companionMessages.push({role:"assistant", content:result.data.reply});
      await refresh({quiet:true});
    } catch (error) {
      state.companionMessages.push({role:"assistant", content:t("I couldn't do that: {{message}}", {message: error.message})});
    } finally {
      state.companionBusy = false;
      render();
    }
    return;
  }
  if (event.target.id !== "tokenGate") return;
  event.preventDefault();
  state.token = new FormData(event.target).get("token").trim();
  localStorage.setItem("focus_api_token", state.token);
  await refresh();
});

document.querySelector("#notifyButton").addEventListener("click", enableNotifications);
document.querySelector("#todayLabel").textContent = formatFocusDate(new Date());
document.addEventListener("focus:locale-change", () => {
  document.querySelector("#todayLabel").textContent = formatFocusDate(new Date());
  if (state.data) render();
  else if (state.meta?.auth_required && !state.token) app.innerHTML = renderTokenGate();
});

setInterval(() => {
  const session = state.data?.active_session;
  if (!session || session.status !== "running") return;
  syncClock();
  state.clock.seconds += 1;
  const element = document.querySelector("#timerValue");
  if (element) element.textContent = timerValue(session);
}, 1000);
setInterval(() => refresh({quiet:true}), 10000);

(async function boot() {
  state.meta = await fetch("/api/meta").then(response => response.json()).catch(() => null);
  if (state.meta?.auth_required && state.meta?.local_only && !state.token) {
    const local = await fetch("/api/local-session", {method:"POST"}).then(response => response.ok ? response.json() : null).catch(() => null);
    if (local?.token) {
      state.token = local.token;
      localStorage.setItem("focus_api_token", state.token);
    }
  }
  if (state.meta?.auth_required && !state.token) app.innerHTML = renderTokenGate();
  else await refresh();
})();
