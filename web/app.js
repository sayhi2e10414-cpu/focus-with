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
const fmtMinutes = seconds => `${Math.round(Number(seconds || 0) / 60)} min`;
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
    throw new AuthError("Focus needs the API token generated during installation.");
  }
  const result = await response.json().catch(() => ({detail: response.statusText}));
  if (!response.ok) throw new Error(result.detail || "Focus request failed");
  return result;
}

async function refresh({quiet = false} = {}) {
  try {
    const result = await api("/api/bootstrap");
    state.data = result.data;
    render();
    handleNotifications(result.data.notifications || []);
  } catch (error) {
    if (!quiet) app.innerHTML = error instanceof AuthError ? renderTokenGate() : `<section class="card error-card"><h2>Focus could not load</h2><p>${esc(error.message)}</p><button class="primary" data-action="retry">Try again</button></section>`;
  }
}

function renderTokenGate() {
  return `<section class="card error-card"><div class="eyebrow">Private by default</div><h2>Connect this browser</h2><p>Paste the API token created by the installer. It stays only in this browser.</p><form id="tokenGate" class="token-form"><input name="token" type="password" autocomplete="off" required placeholder="Focus API token"><button class="primary">Connect</button></form></section>`;
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
  return state.data.projects.find(item => item.id === projectId)?.title || "No project";
}

function directionName(directionId) {
  return state.data.directions.find(item => item.id === directionId)?.title || "Independent";
}

function renderTimer() {
  const session = state.data.active_session;
  const policyApps = state.data.policy.blocked_apps || [];
  if (!session) return `
    <section class="card timer-card idle">
      <div class="eyebrow">Ready when you are</div>
      <h2 class="timer-title">Start with one clear task.</h2>
      <p class="timer-goal">Choose something from today, or create a free-focus session.</p>
      <div class="timer-value">25:00</div>
      <div class="timer-state">No active session</div>
      <div class="timer-actions"><button class="primary" data-action="free-focus">Start free focus</button></div>
      <div class="monitor-note"><span class="dot"></span>${esc(policyApps.join(", ") || "Distraction monitoring is off")}</div>
    </section>`;
  const task = state.data.tasks.find(item => item.id === session.task_id);
  const label = task?.title || session.goal || session.title || "Free focus";
  return `
    <section class="card timer-card">
      <div class="eyebrow">${session.status === "paused" ? "Paused" : "Focusing"}</div>
      <h2 class="timer-title">${esc(label)}</h2>
      <p class="timer-goal">${esc(task?.details || projectName(session.project_id))}</p>
      <div class="timer-value" id="timerValue">${timerValue(session)}</div>
      <div class="timer-state">${session.status === "paused" ? "Take a breath, then decide." : session.mode}</div>
      <div class="timer-actions">
        <button class="primary" data-session-action="${session.status === "paused" ? "resume" : "pause"}">${session.status === "paused" ? "Resume" : "Pause"}</button>
        <button class="secondary" data-session-action="complete">End session</button>
      </div>
      <div class="monitor-note"><span class="dot"></span>${esc(policyApps.join(", ") || "No apps monitored")} · one strike per distinct open</div>
    </section>`;
}

function renderTaskRow(task) {
  return `<div class="task-row">
    <button class="task-check" data-complete-task="${task.id}" aria-label="Complete ${esc(task.title)}"></button>
    <div class="task-copy"><strong>${esc(task.title)}</strong><span>${esc(projectName(task.project_id))} · ${task.estimated_minutes} min${task.details ? ` · ${esc(task.details)}` : ""}</span></div>
    <div class="task-tools"><button data-start-task="${task.id}">Start</button><button data-edit-task="${task.id}">•••</button></div>
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
      <div class="section-head"><div><div class="eyebrow">Today</div><h2>Your focus list</h2></div><button class="ghost" data-action="new-task">Add</button></div>
      <div class="summary-grid">
        <div class="summary-item"><strong>${stats.focus_minutes}</strong><span>minutes</span></div>
        <div class="summary-item"><strong>${stats.completed_tasks}</strong><span>completed</span></div>
        <div class="summary-item"><strong>${stats.session_count}</strong><span>sessions</span></div>
        <div class="summary-item"><strong>${stats.interruptions}</strong><span>interruptions</span></div>
      </div>
      <div class="progress"><span style="width:${total ? Math.round(done / total * 100) : 0}%"></span></div>
      <div class="task-list">${open.length ? open.map(renderTaskRow).join("") : `<div class="empty">Nothing pending. Make space for rest.</div>`}</div>
    </section>
  </div>`;
}

function renderProjects() {
  const directions = state.data.directions.filter(item => item.status !== "archived").map(direction => {
    const count = state.data.projects.filter(project => project.direction_id === direction.id && project.status !== "archived").length;
    return `<div class="direction-item"><div><span>Direction</span><strong>${esc(direction.title)}</strong><p>${esc(direction.goal || "A longer-term area worth moving forward.")}</p></div><b>${count} ${count === 1 ? "project" : "projects"}</b></div>`;
  }).join("");
  const cards = state.data.projects.filter(item => item.status !== "archived").map(project => {
    const tasks = state.data.tasks.filter(task => task.project_id === project.id);
    const done = tasks.filter(task => task.status === "done").length;
    const percent = tasks.length ? Math.round(done / tasks.length * 100) : 0;
    return `<section class="card page-card project-card">
      <div class="eyebrow">${esc(directionName(project.direction_id))} · ${esc(project.status)}</div><h2>${esc(project.title)}</h2>
      <p class="project-meta">${esc(project.outcome || "Define what done looks like.")}</p>
      <div class="progress"><span style="width:${percent}%"></span></div>
      <div class="project-footer"><span>${done} / ${tasks.length} tasks</span><button class="ghost" data-action="new-task" data-project="${project.id}">Add task</button></div>
    </section>`;
  }).join("");
  return `<div class="section-head"><div><div class="eyebrow">Structure</div><h2>Directions and projects</h2></div><div class="top-actions"><button class="secondary" data-action="new-direction">New direction</button><button class="primary" data-action="new-project">＋ New project</button></div></div>
    <div class="direction-strip">${directions || `<div class="direction-item"><div><span>Direction</span><strong>Choose a longer-term direction</strong><p>Projects can live inside it, while one-off projects stay independent.</p></div></div>`}</div>
    <div class="page-grid">${cards || `<section class="card empty">Create your first project.</section>`}</div>`;
}

function renderStats() {
  const today = state.data.stats.today;
  const week = state.data.stats.week;
  const grouped = week.by_activity || [];
  return `<div class="page-grid">
    <section class="card page-card stat-hero">
      <div class="stat-block"><strong>${today.focus_minutes}</strong><span>focused minutes today</span></div>
      <div class="stat-block"><strong>${today.session_count}</strong><span>sessions today</span></div>
      <div class="stat-block"><strong>${week.focus_minutes}</strong><span>minutes this week</span></div>
    </section>
    <section class="card page-card"><div class="section-head"><div><div class="eyebrow">This week</div><h2>By activity</h2></div></div>
      <div class="task-list">${grouped.map(row => `<div class="task-row"><div></div><div class="task-copy"><strong>${esc(row.title)}</strong><span>${fmtMinutes(row.focus_seconds)} · ${row.session_count} ${row.session_count === 1 ? "session" : "sessions"}</span></div></div>`).join("") || `<div class="empty">No sessions yet.</div>`}</div>
    </section>
    <section class="card page-card"><div class="section-head"><div><div class="eyebrow">Distractions</div><h2>Interventions</h2></div></div>
      <div class="task-list">${state.data.interventions.slice(0,10).map(row => `<div class="task-row"><div></div><div class="task-copy"><strong>${esc(row.app_name)} · ${row.strike_number}</strong><span>${esc(row.status)} · ${fmtMinutes(row.duration_seconds)}</span></div></div>`).join("") || `<div class="empty">No distraction events.</div>`}</div>
    </section>
  </div>`;
}

function renderSettings() {
  const policy = state.data.policy;
  const provider = state.meta?.ai_provider || "none";
  return `<div class="page-grid">
    <section class="card page-card"><div class="section-head"><div><div class="eyebrow">Focus policy</div><h2>Distraction rules</h2></div><button class="ghost" data-action="edit-policy">Edit</button></div>
      <div class="settings-list">
        <div class="settings-row"><div><strong>Monitored apps</strong><span>One strike per distinct app opening</span></div><div class="chips">${policy.blocked_apps.map(app => `<span class="chip">${esc(app)}</span>`).join("") || `<span class="chip">None</span>`}</div></div>
        <div class="settings-row"><div><strong>Grace period</strong><span>Ignore brief accidental opens</span></div><b>${policy.grace_seconds}s</b></div>
        <div class="settings-row"><div><strong>Punishment threshold</strong><span>Distinct openings within one session</span></div><b>${policy.strikes_for_punishment}</b></div>
      </div>
    </section>
    <section class="card page-card"><div class="section-head"><div><div class="eyebrow">Connections</div><h2>Optional integrations</h2></div></div>
      <div class="settings-list">
        <div class="settings-row"><div><strong>AI companion</strong><span>Configured during installation</span></div><b>${esc(provider)}</b></div>
        <div class="settings-row"><div><strong>Telegram</strong><span>Optional delivery channel</span></div><b>${state.meta?.telegram_enabled ? "On" : "Off"}</b></div>
        <div class="settings-row"><div><strong>Browser notifications</strong><span>Timer and distraction reminders</span></div><button class="secondary" data-action="notifications">Enable</button></div>
        <div class="settings-row"><div><strong>API token</strong><span>Stored only in this browser</span></div><button class="secondary" data-action="change-token">Change</button></div>
      </div>
    </section>
  </div>`;
}

function renderCompanion() {
  const enabled = Boolean(state.meta?.ai_enabled);
  const messages = state.companionMessages.map(item => `
    <div class="chat-message ${item.role}"><span>${item.role === "user" ? "You" : "Focus"}</span><p>${esc(item.content).replace(/\n/g, "<br>")}</p></div>`).join("");
  return `<section class="card companion-card">
    <div class="section-head"><div><div class="eyebrow">Optional · ${esc(state.meta?.ai_provider || "none")}</div><h2>Focus companion</h2></div><span class="chip">${enabled ? esc(state.meta.ai_model) : "Off"}</span></div>
    ${enabled ? `<div class="chat-thread" id="chatThread">${messages || `<div class="companion-empty"><strong>What should we focus on?</strong><p>I can read your current plan, create or rearrange tasks, and start the timer.</p></div>`}</div>
      <form class="chat-form" id="companionForm"><textarea name="message" rows="2" required placeholder="Plan my next hour…" ${state.companionBusy ? "disabled" : ""}></textarea><button class="primary" ${state.companionBusy ? "disabled" : ""}>${state.companionBusy ? "Thinking…" : "Send"}</button></form>`
      : `<div class="companion-empty"><strong>No model is connected.</strong><p>Focus works without AI. To add one, set the provider, model, and API key in <code>.env</code>, then restart Focus.</p></div>`}
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

function openModal({title, eyebrow = "Focus", body, submit = "Save", onSubmit}) {
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
  const projects = [["", "No project"], ...state.data.projects.map(item => [item.id, item.title])];
  openModal({
    title: task ? "Edit task" : "New task", eyebrow: "Task", submit: task ? "Save task" : "Create task",
    body: `${field("Title", "title", task?.title || "", "text", "required autofocus")}
      <label class="field"><span>Details</span><textarea name="details" rows="3">${esc(task?.details || "")}</textarea></label>
      ${selectField("Project", "project_id", projects, task?.project_id || defaultProject || "")}
      <div class="form-grid">${field("Minutes", "estimated_minutes", task?.estimated_minutes || 25, "number", "min=1")}${selectField("Priority", "priority", [[1,"High"],[2,"Important"],[3,"Normal"],[4,"Low"],[5,"Someday"]], task?.priority || 3)}</div>
      ${field("Monitored apps", "blocked_apps", (task?.blocked_apps || []).join(", "), "text", "placeholder='Leave blank to use global policy'")}
      ${task ? `<button type="button" class="danger" data-abandon-task="${task.id}">Abandon task</button>` : ""}`,
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
  const directions = [["", "Independent project"], ...state.data.directions.map(item => [item.id, item.title])];
  openModal({title: "New project", eyebrow: "Project", submit: "Create project", body: `${field("Project name", "title", "", "text", "required autofocus")}<label class="field"><span>Desired outcome</span><textarea name="outcome" rows="3"></textarea></label>${selectField("Direction", "direction_id", directions, "")}${field("Weekly target", "weekly_target_minutes", 0, "number", "min=0")}`,
    onSubmit: form => api("/api/projects", {method:"POST", body:JSON.stringify({direction_id:form.direction_id?Number(form.direction_id):null,title:form.title.trim(),outcome:form.outcome.trim()||null,notes:null,status:"active",weekly_target_minutes:Number(form.weekly_target_minutes||0),target_minutes:0,due_date:null,sort_order:state.data.projects.length})})});
}

function directionModal() {
  openModal({title:"New direction",eyebrow:"Long-term",submit:"Create direction",body:`${field("Direction name","title","","text","required autofocus")}<label class="field"><span>What should this direction change?</span><textarea name="goal" rows="3"></textarea></label>${field("Weekly target minutes","weekly_target_minutes",0,"number","min=0")}`,onSubmit:form=>api("/api/directions",{method:"POST",body:JSON.stringify({title:form.title.trim(),goal:form.goal.trim()||null,status:"active",weekly_target_minutes:Number(form.weekly_target_minutes||0),sort_order:state.data.directions.length})})});
}

function importPlanModal() {
  const projects = [["", "No project"], ...state.data.projects.map(item => [item.id, item.title])];
  openModal({
    title:"Import a GPT plan", eyebrow:"Markdown", submit:"Import tasks",
    body:`<label class="field"><span>Paste the plan</span><textarea name="markdown" rows="12" required autofocus placeholder="1. Read the chapter | 25 min\n2. Make a comparison table | 35 min"></textarea></label>${selectField("Assign every task to", "project_id", projects, "")}`,
    onSubmit:async form=>{
      const result = await api("/api/plans/import", {method:"POST", body:JSON.stringify({markdown:form.markdown,project_id:form.project_id?Number(form.project_id):null,target_date:null})});
      const breaks = result.data.breaks.length;
      showToast(`Imported ${result.data.tasks.length} tasks${breaks ? ` · recognized ${breaks} break` : ""}.`);
    },
  });
}

function policyModal() {
  const policy = state.data.policy;
  openModal({title:"Distraction rules",eyebrow:"Policy",body:`${field("Monitored apps", "blocked_apps", policy.blocked_apps.join(", "), "text", "placeholder='Instagram, TikTok'")}<div class="form-grid">${field("Grace seconds","grace_seconds",policy.grace_seconds,"number","min=15")}${field("Punishment after","strikes_for_punishment",policy.strikes_for_punishment,"number","min=1")}</div>${field("Reminder cooldown seconds","reminder_cooldown_seconds",policy.reminder_cooldown_seconds,"number","min=30")}<label class="field"><span>Punishment pool · one per line</span><textarea name="punishment_pool" rows="4">${esc(policy.punishment_pool.join("\n"))}</textarea></label>`,onSubmit:form=>api("/api/policy",{method:"PUT",body:JSON.stringify({blocked_apps:form.blocked_apps.split(/[,，]/).map(x=>x.trim()).filter(Boolean),grace_seconds:Number(form.grace_seconds),strikes_for_punishment:Number(form.strikes_for_punishment),reminder_cooldown_seconds:Number(form.reminder_cooldown_seconds),punishment_pool:form.punishment_pool.split("\n").map(x=>x.trim()).filter(Boolean)})})});
}

function tokenModal() {
  openModal({title:"Connect this browser",eyebrow:"Security",submit:"Save token",body:field("Focus API token","token",state.token,"password","required autocomplete='off'"),onSubmit:async form=>{state.token=form.token.trim();localStorage.setItem("focus_api_token",state.token);}});
}

function freeFocusModal() {
  openModal({title:"Start free focus",eyebrow:"Timer",submit:"Start",body:`${field("Title","title","Free focus","text","required autofocus")}${field("Minutes","minutes",25,"number","min=1 max=1440")}`,onSubmit:form=>api("/api/sessions",{method:"POST",body:JSON.stringify({task_id:null,project_id:null,session_kind:"work",mode:"pomodoro",title:form.title.trim(),goal:null,planned_minutes:Number(form.minutes||25)})})});
}

async function enableNotifications() {
  if (!("Notification" in window)) return showToast("This browser does not support notifications.");
  const result = await Notification.requestPermission();
  showToast(result === "granted" ? "Browser notifications enabled." : "Notifications were not enabled.");
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
    showToast(result.data.next_task ? `Done. Next: ${result.data.next_task.title}` : "Done. Your list is clear.");
    return refresh();
  }
  const abandonId = event.target.closest("[data-abandon-task]")?.dataset.abandonTask;
  if (abandonId) { await api(`/api/tasks/${abandonId}/abandon`, {method:"POST"}); modal.close(); showToast("Task abandoned."); return refresh(); }
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
      state.companionMessages.push({role:"assistant", content:`I couldn't do that: ${error.message}`});
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
document.querySelector("#todayLabel").textContent = new Intl.DateTimeFormat(undefined, {weekday:"long",month:"long",day:"numeric"}).format(new Date());

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
