// The frontend talks to the API through the SAME origin ("/api/...").
// Whatever serves this page must forward /api to the backend service.
const list = document.getElementById("tasks");
const errorBox = document.getElementById("error");

async function api(path, options = {}) {
  const resp = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(body.error || `Request failed (${resp.status})`);
  }
  return resp.status === 204 ? null : resp.json();
}

function render(tasks) {
  list.innerHTML = "";
  for (const t of tasks) {
    const li = document.createElement("li");
    li.className = t.status;

    const title = document.createElement("span");
    title.textContent = t.title;

    const select = document.createElement("select");
    for (const s of ["todo", "in_progress", "done"]) {
      const opt = document.createElement("option");
      opt.value = s;
      opt.textContent = s.replace("_", " ");
      opt.selected = s === t.status;
      select.appendChild(opt);
    }
    select.addEventListener("change", () =>
      run(() => api(`/api/tasks/${t.id}`, { method: "PUT", body: JSON.stringify({ status: select.value }) }))
    );

    const del = document.createElement("button");
    del.className = "del";
    del.textContent = "x";
    del.addEventListener("click", () => run(() => api(`/api/tasks/${t.id}`, { method: "DELETE" })));

    li.append(title, select, del);
    list.appendChild(li);
  }
}

async function load() {
  render(await api("/api/tasks"));
}

async function run(action) {
  errorBox.textContent = "";
  try {
    await action();
    await load();
  } catch (e) {
    errorBox.textContent = e.message;
  }
}

document.getElementById("new-task").addEventListener("submit", (e) => {
  e.preventDefault();
  const input = document.getElementById("title");
  run(async () => {
    await api("/api/tasks", { method: "POST", body: JSON.stringify({ title: input.value }) });
    input.value = "";
  });
});

run(load);
