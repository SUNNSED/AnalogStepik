const ROUTES = [
  { group: "Auth", method: "POST", path: "/auth/register", label: "Регистрация" },
  { group: "Auth", method: "POST", path: "/auth/login", label: "Получить токены" },
  { group: "Auth", method: "POST", path: "/auth/refresh", label: "Обновить токены" },
  { group: "Users", method: "GET", path: "/users/", label: "Список пользователей" },
  { group: "Users", method: "GET", path: "/users/me", label: "Мой профиль" },
  { group: "Users", method: "PUT", path: "/users/me", label: "Обновить профиль" },
  { group: "Users", method: "GET", path: "/users/me/stats", label: "Моя статистика" },
  { group: "Users", method: "GET", path: "/users/students/progress", label: "Прогресс учеников" },
  { group: "Users", method: "GET", path: "/users/{user_id}", label: "Профиль по ID" },
  { group: "Users", method: "DELETE", path: "/users/{user_id}", label: "Удалить пользователя" },
  { group: "Courses", method: "GET", path: "/courses/", label: "Все курсы" },
  { group: "Courses", method: "GET", path: "/courses/my", label: "Мои курсы" },
  { group: "Courses", method: "GET", path: "/courses/my/created", label: "Курсы автора" },
  { group: "Courses", method: "GET", path: "/courses/{course_id}", label: "Детали курса" },
  { group: "Courses", method: "POST", path: "/courses/", label: "Создать курс" },
  { group: "Courses", method: "PUT", path: "/courses/{course_id}", label: "Обновить курс" },
  { group: "Courses", method: "DELETE", path: "/courses/{course_id}", label: "Удалить курс" },
  { group: "Courses", method: "POST", path: "/courses/{course_id}/enroll", label: "Записаться" },
  { group: "Courses", method: "POST", path: "/courses/{course_id}/unenroll", label: "Отписаться" },
  { group: "Tasks", method: "GET", path: "/tasks/", label: "Все задачи" },
  { group: "Tasks", method: "GET", path: "/tasks/{task_id}", label: "Задача по ID" },
  { group: "Tasks", method: "POST", path: "/tasks/", label: "Создать задачу" },
  { group: "Submissions", method: "POST", path: "/submissions/", label: "Отправить решение" },
  { group: "Submissions", method: "GET", path: "/submissions/{submission_id}", label: "Статус отправки" },
  { group: "Root", method: "GET", path: "/", label: "Health check" },
];

const viewMeta = {
  dashboard: ["Обзор", "Рабочая панель"],
  courses: ["Курсы", "Каталог и запись"],
  learning: ["Моё обучение", "Активные курсы"],
  tasks: ["Задачи", "Условия и отправка кода"],
  submissions: ["Отправки", "Статусы проверок"],
  teacher: ["Кабинет автора", "Курсы и задачи"],
  progress: ["Прогресс", "Ученики и группы"],
  users: ["Пользователи", "Профили"],
  routes: ["API", "Карта backend-роутов"],
};

const state = {
  apiBase: localStorage.getItem("analogstepik.apiBase") || "http://localhost:8000",
  accessToken: localStorage.getItem("analogstepik.accessToken") || "",
  refreshToken: localStorage.getItem("analogstepik.refreshToken") || "",
  profile: null,
  stats: null,
  courses: [],
  myCourses: [],
  createdCourses: [],
  tasks: [],
  users: [],
  progressReports: [],
  selectedCourse: null,
  selectedTask: null,
  selectedTaskCourseId: "",
  selectedTaskId: null,
  selectedSubmissionId: null,
  lastSubmissions: readJson("analogstepik.lastSubmissions", []),
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

function readJson(key, fallback) {
  try {
    return JSON.parse(localStorage.getItem(key)) ?? fallback;
  } catch {
    return fallback;
  }
}

function saveSession(tokens) {
  state.accessToken = tokens.access_token;
  state.refreshToken = tokens.refresh_token;
  localStorage.setItem("analogstepik.accessToken", state.accessToken);
  localStorage.setItem("analogstepik.refreshToken", state.refreshToken);
}

function clearSession() {
  state.accessToken = "";
  state.refreshToken = "";
  state.profile = null;
  state.stats = null;
  state.users = [];
  state.progressReports = [];
  state.tasks = [];
  state.selectedTask = null;
  state.selectedTaskCourseId = "";
  state.selectedTaskId = null;
  localStorage.removeItem("analogstepik.accessToken");
  localStorage.removeItem("analogstepik.refreshToken");
}

function setApiBase(value) {
  state.apiBase = value.replace(/\/+$/, "");
  localStorage.setItem("analogstepik.apiBase", state.apiBase);
  $("#apiBaseAuth").value = state.apiBase;
  $("#apiBaseApp").value = state.apiBase;
}

async function api(path, options = {}, retry = true) {
  const url = `${state.apiBase}${path}`;
  const headers = new Headers(options.headers || {});
  headers.set("Accept", "application/json");

  const init = { method: options.method || "GET", headers };

  if (options.auth !== false && state.accessToken) {
    headers.set("Authorization", `Bearer ${state.accessToken}`);
  }

  if (options.form) {
    headers.set("Content-Type", "application/x-www-form-urlencoded");
    init.body = new URLSearchParams(options.form);
  } else if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
    init.body = JSON.stringify(options.body);
  }

  const response = await fetch(url, init);
  const payload = await parseResponse(response);

  if ((response.status === 401 || response.status === 403) && retry && state.refreshToken && path !== "/auth/refresh") {
    try {
      await refreshTokens();
      return api(path, options, false);
    } catch {
      clearSession();
      renderSession();
    }
  }

  if (!response.ok) {
    const detail = payload?.detail || response.statusText || "Request failed";
    throw new Error(Array.isArray(detail) ? JSON.stringify(detail, null, 2) : detail);
  }

  return payload;
}

async function parseResponse(response) {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function refreshTokens() {
  if (!state.refreshToken) {
    throw new Error("Нет refresh token");
  }

  const tokens = await api("/auth/refresh", {
    method: "POST",
    body: { refresh_token: state.refreshToken },
    auth: false,
  }, false);

  saveSession(tokens);
  renderSession();
  return tokens;
}

function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.add("is-visible");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.remove("is-visible"), 2800);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatDate(value) {
  if (!value) return "-";
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function statusBadge(status) {
  const normalized = String(status || "").toLowerCase();
  const cls = normalized === "correct" ? "ok" : normalized === "pending" ? "warn" : "bad";
  return `<span class="badge ${cls}">${escapeHtml(status || "-")}</span>`;
}

function renderSession() {
  const isAuthed = Boolean(state.accessToken);
  const isAdmin = Boolean(state.profile?.is_admin);
  const isTeacher = Boolean(state.profile?.is_teacher || isAdmin);
  $("#authLayout").classList.toggle("is-hidden", isAuthed);
  $("#appShell").classList.toggle("is-hidden", !isAuthed);
  $("#sessionChip").textContent = state.profile ? state.profile.email : "Сессия активна";
  $("#roleLabel").textContent = isAdmin ? "админ" : isTeacher ? "автор курса" : "ученик";
  $$("[data-teacher-only]").forEach((element) => element.classList.toggle("is-hidden", !isTeacher));
  $$("[data-admin-only]").forEach((element) => element.classList.toggle("is-hidden", !isAdmin));

  if (isAuthed && !isTeacher && ($("#view-teacher")?.classList.contains("is-active") || $("#view-progress")?.classList.contains("is-active"))) {
    switchView("dashboard");
  }

  if (isAuthed && !isAdmin && ($("#view-users")?.classList.contains("is-active") || $("#view-routes")?.classList.contains("is-active"))) {
    switchView("dashboard");
  }
}

function renderProfile() {
  const profile = state.profile;
  const html = profile
    ? `
      <div class="meta-row">
        <span class="badge">ID ${profile.id}</span>
        <span class="badge ${profile.is_active ? "ok" : "bad"}">${profile.is_active ? "активен" : "заблокирован"}</span>
        <span class="badge ${profile.is_admin ? "bad" : profile.is_teacher ? "warn" : ""}">${profile.is_admin ? "admin" : profile.is_teacher ? "teacher" : "student"}</span>
      </div>
      <h3 class="detail-title">${escapeHtml(profile.email)}</h3>
      <p class="muted">${escapeHtml([profile.last_name, profile.first_name].filter(Boolean).join(" ") || "Имя не заполнено")}</p>
      <p class="muted">Группа: ${escapeHtml(profile.group_number || "-")}</p>
      <p class="muted">Создан: ${formatDate(profile.created_at)}</p>
      <p class="muted">Записан на курсов: ${profile.enrolled_courses?.length || 0}</p>
    `
    : `<p class="muted">Профиль не загружен.</p>`;
  $("#profileBox").innerHTML = html;
  if ($("#currentUserMirror")) {
    $("#currentUserMirror").innerHTML = html;
  }

  const form = $("#profileForm");
  if (form && profile) {
    form.elements.first_name.value = profile.first_name || "";
    form.elements.last_name.value = profile.last_name || "";
    form.elements.group_number.value = profile.group_number || "";
  }
}

function renderStats() {
  const stats = state.stats || {};
  $("#statTotal").textContent = stats.total_submissions ?? 0;
  $("#statCorrect").textContent = stats.correct_submissions ?? 0;
  $("#statAccuracy").textContent = `${stats.accuracy ?? 0}%`;
  $("#statCourses").textContent = stats.courses_enrolled ?? 0;
}

function renderCourses() {
  $("#coursesList").innerHTML = state.courses.map((course) => `
    <article class="list-item">
      <div class="list-item-head">
        <div>
          <h4>${escapeHtml(course.title)}</h4>
          <p>${escapeHtml(course.description)}</p>
        </div>
        ${course.is_enrolled ? `<span class="badge ok">записан</span>` : `<span class="badge">доступен</span>`}
      </div>
      <div class="meta-row">
        <span class="badge">ID ${course.id}</span>
        <span class="badge">teacher ${course.teacher_id}</span>
        <button class="soft-btn" type="button" data-open-course="${course.id}">Открыть</button>
      </div>
    </article>
  `).join("") || empty("Курсов пока нет.");
}

function renderMyCourses() {
  $("#myCoursesList").innerHTML = state.myCourses.map((course) => `
    <article class="course-card">
      <div class="meta-row">
        <span class="badge ok">записан</span>
        <span class="badge">ID ${course.id}</span>
      </div>
      <h4>${escapeHtml(course.title)}</h4>
      <p>${escapeHtml(course.description)}</p>
      <button class="soft-btn" type="button" data-open-course="${course.id}" data-view-target="courses">Открыть</button>
    </article>
  `).join("") || empty("Ты пока не записан на курсы.");
}

function renderCreatedCourses() {
  $("#createdCoursesList").innerHTML = state.createdCourses.map((course) => `
    <article class="list-item">
      <div class="list-item-head">
        <div>
          <h4>${escapeHtml(course.title)}</h4>
          <p>${escapeHtml(course.description)}</p>
        </div>
        <span class="badge">ID ${course.id}</span>
      </div>
      <div class="button-row">
        <button class="soft-btn" type="button" data-fill-course="${course.id}">Редактировать</button>
        <button class="ghost-btn" type="button" data-open-course="${course.id}" data-view-target="courses">Открыть</button>
      </div>
    </article>
  `).join("") || empty("Созданных курсов нет или нет прав teacher.");
  renderTaskCourseOptions();
}

function renderTaskCourseOptions() {
  const courses = state.createdCourses.length ? state.createdCourses : state.courses;
  const currentValue = $("#taskCourseSelect").value;
  $("#taskCourseSelect").innerHTML = `<option value="">Без курса</option>` + courses.map((course) =>
    `<option value="${course.id}">${escapeHtml(course.title)}</option>`
  ).join("");
  if ([...$("#taskCourseSelect").options].some((option) => option.value === currentValue)) {
    $("#taskCourseSelect").value = currentValue;
  }
}

function getTaskFilterCourses() {
  const isAdmin = Boolean(state.profile?.is_admin);
  const isTeacher = Boolean(state.profile?.is_teacher || isAdmin);

  if (isAdmin) return state.courses;
  if (isTeacher) return state.createdCourses;
  return state.myCourses.length ? state.myCourses : state.courses.filter((course) => course.is_enrolled);
}

function renderTaskCourseFilter() {
  const select = $("#taskCourseFilter");
  if (!select) return;

  const courses = getTaskFilterCourses();
  const currentValue = state.selectedTaskCourseId || select.value;
  select.innerHTML = `<option value="">${courses.length ? "Сначала выбери курс" : "Нет доступных курсов"}</option>` + courses.map((course) =>
    `<option value="${course.id}">${escapeHtml(course.title)}</option>`
  ).join("");

  if ([...select.options].some((option) => option.value === currentValue)) {
    select.value = currentValue;
    state.selectedTaskCourseId = currentValue;
  } else {
    select.value = "";
    state.selectedTaskCourseId = "";
  }
}

function renderCourseDetail() {
  const course = state.selectedCourse;
  if (!course) {
    $("#courseDetail").innerHTML = `<p class="muted">Выбери курс из списка.</p>`;
    return;
  }

  const tasks = course.tasks || [];
  $("#courseDetail").innerHTML = `
    <div class="meta-row">
      <span class="badge">ID ${course.id}</span>
      <span class="badge">${course.students_count ?? 0} студентов</span>
      ${course.is_enrolled ? `<span class="badge ok">записан</span>` : `<span class="badge">не записан</span>`}
    </div>
    <h3 class="detail-title">${escapeHtml(course.title)}</h3>
    <p class="description">${escapeHtml(course.description)}</p>
    <div class="item-list">
      ${tasks.map((task) => `
        <article class="list-item">
          <div class="list-item-head">
            <div>
              <h4>${escapeHtml(task.title)}</h4>
              <p>${escapeHtml(shortText(task.description, 130))}</p>
            </div>
            <span class="badge">${task.test_cases?.length || 0} тестов</span>
          </div>
          <button class="soft-btn" type="button" data-open-task="${task.id}" data-view-target="tasks">Решать</button>
        </article>
      `).join("") || empty("В курсе пока нет задач.")}
    </div>
  `;
}

function renderTasks() {
  if (!state.selectedTaskCourseId) {
    $("#tasksList").innerHTML = empty("Сначала выбери курс.");
    return;
  }

  $("#tasksList").innerHTML = state.tasks.map((task) => `
    <article class="list-item task-card ${String(task.id) === String(state.selectedTaskId) ? "is-selected" : ""}" data-open-task="${task.id}" tabindex="0" role="button" aria-current="${String(task.id) === String(state.selectedTaskId) ? "true" : "false"}">
      <div class="list-item-head">
        <div>
          <h4>${escapeHtml(task.title)}</h4>
          <p>${escapeHtml(shortText(task.description, 120))}</p>
        </div>
        <span class="badge">ID ${task.id}</span>
      </div>
      <div class="meta-row">
        <span class="badge">курс ${task.course_id ?? "-"}</span>
        <span class="badge">${task.test_cases?.length || 0} тестов</span>
      </div>
    </article>
  `).join("") || empty("В выбранном курсе пока нет задач.");
}

function renderTaskDetail() {
  const task = state.selectedTask;
  if (!task) {
    $("#taskDetail").innerHTML = `<p class="muted">Выбери задачу.</p>`;
    $("#submissionForm").classList.add("is-hidden");
    return;
  }

  $("#submissionForm").classList.remove("is-hidden");
  $("#submissionForm").elements.task_id.value = task.id;
  if ($("#taskLookupId")) {
    $("#taskLookupId").value = task.id;
  }

  $("#taskDetail").innerHTML = `
    <div class="meta-row">
      <span class="badge">ID ${task.id}</span>
      <span class="badge">курс ${task.course_id ?? "-"}</span>
      <span class="badge">${task.test_cases?.length || 0} тестов</span>
    </div>
    <h3 class="detail-title">${escapeHtml(task.title)}</h3>
    <p class="description">${escapeHtml(task.description)}</p>
    <div class="item-list">
      ${(task.test_cases || []).map((test, index) => `
        <article class="list-item">
          <div class="list-item-head">
            <h4>Тест ${index + 1}</h4>
            ${test.is_hidden ? `<span class="badge warn">скрытый</span>` : `<span class="badge ok">открытый</span>`}
          </div>
          ${test.is_hidden ? `<p class="muted">Данные скрыты для ученика.</p>` : `
            <pre class="result-box">stdin:
${escapeHtml(test.input_data || "(пусто)")}

expected:
${escapeHtml(test.expected_output || "")}</pre>
          `}
        </article>
      `).join("")}
    </div>
  `;
}

function renderLocalSubmissions() {
  $("#localSubmissionsList").innerHTML = state.lastSubmissions.map((item) => `
    <article class="list-item ${String(item.id) === String(state.selectedSubmissionId) ? "is-selected" : ""}" aria-current="${String(item.id) === String(state.selectedSubmissionId) ? "true" : "false"}">
      <div class="list-item-head">
        <div>
          <h4>Submission ${item.id}</h4>
          <p>Задача ${item.task_id} · ${formatDate(item.created_at)}</p>
        </div>
        ${statusBadge(item.status)}
      </div>
      <button class="soft-btn" type="button" data-open-submission="${item.id}">Открыть</button>
    </article>
  `).join("") || empty("Здесь будут отправки, созданные из этого браузера.");
}

function renderRoutes() {
  $("#routesMap").innerHTML = ROUTES.map((route) => `
    <article class="route-card">
      <div class="meta-row">
        <span class="badge ${route.method === "GET" ? "ok" : route.method === "DELETE" ? "bad" : "warn"}">${route.method}</span>
        <span class="badge">${route.group}</span>
      </div>
      <h4>${route.label}</h4>
      <code>${route.path}</code>
    </article>
  `).join("");
}

function renderUsers() {
  $("#usersList").innerHTML = state.users.map((user) => `
    <article class="list-item">
      <div class="list-item-head">
        <div>
          <h4>${escapeHtml(user.email)}</h4>
          <p>${escapeHtml([user.last_name, user.first_name].filter(Boolean).join(" ") || "Имя не заполнено")}</p>
        </div>
        <span class="badge ${user.is_admin ? "bad" : user.is_teacher ? "warn" : ""}">${user.is_admin ? "admin" : user.is_teacher ? "teacher" : "student"}</span>
      </div>
      <div class="meta-row">
        <span class="badge">ID ${user.id}</span>
        <span class="badge">группа ${escapeHtml(user.group_number || "-")}</span>
        <button class="soft-btn" type="button" data-open-user="${user.id}">Открыть</button>
        <button class="danger-btn" type="button" data-delete-user="${user.id}">Удалить</button>
      </div>
    </article>
  `).join("") || empty("Пользователи не найдены.");
}

function renderProgressCourseDetail(course) {
  if (!course) {
    return `<p class="muted">У ученика нет подходящих записей на курсы.</p>`;
  }

  return `
    <div class="progress-row">
      <div>
        <strong>${escapeHtml(course.title)}</strong>
        <p class="muted">${course.solved_tasks}/${course.total_tasks} задач · ${course.submissions_count} отправок</p>
      </div>
      <div class="progress-track" aria-label="Прогресс ${course.progress_percent}%">
        <div class="progress-fill" style="width: ${Math.max(0, Math.min(100, course.progress_percent))}%"></div>
      </div>
      <span class="badge ${course.progress_percent === 100 ? "ok" : "warn"}">${course.progress_percent}%</span>
    </div>
  `;
}

function renderProgressReports() {
  $("#progressList").innerHTML = state.progressReports.map((report, reportIndex) => {
    const selectedCourse = report.courses[0];

    return `
      <article class="progress-card">
        <div class="list-item-head">
          <div>
            <h4>${escapeHtml(report.user.email)}</h4>
            <p class="muted">${escapeHtml([report.user.last_name, report.user.first_name].filter(Boolean).join(" ") || "Имя не заполнено")} · группа ${escapeHtml(report.user.group_number || "-")}</p>
          </div>
          <span class="badge">ID ${report.user.id}</span>
        </div>
        <div class="progress-courses">
          <label>
            Курс ученика
            <select data-progress-course-select="${reportIndex}">
              ${report.courses.map((course) => `
                <option value="${course.course_id}">${escapeHtml(course.title)}</option>
              `).join("")}
            </select>
          </label>
          <div data-progress-course-detail="${reportIndex}">
            ${renderProgressCourseDetail(selectedCourse)}
          </div>
        </div>
      </article>
    `;
  }).join("") || empty("Ничего не найдено.");
}

function renderTestCasesEditor() {
  const container = $("#testCasesEditor");
  if (!container.children.length) {
    addTestCaseRow("", "", false);
  }
}

function addTestCaseRow(input = "", output = "", hidden = false) {
  const count = $("#testCasesEditor").children.length + 1;
  const card = document.createElement("article");
  card.className = "testcase-card";
  card.innerHTML = `
    <div class="testcase-head">
      <strong>Тест ${count}</strong>
      <button class="ghost-btn" type="button" data-remove-test>Удалить</button>
    </div>
    <div class="form-grid">
      <label>
        Ввод
        <textarea data-test-input rows="3" placeholder="1 2">${escapeHtml(input)}</textarea>
      </label>
      <label>
        Ожидаемый вывод
        <textarea data-test-output rows="3" required placeholder="3">${escapeHtml(output)}</textarea>
      </label>
    </div>
    <label class="checkbox-line">
      <input data-test-hidden type="checkbox" ${hidden ? "checked" : ""} />
      Скрытый тест
    </label>
  `;
  $("#testCasesEditor").append(card);
}

function empty(text) {
  return `<p class="muted">${escapeHtml(text)}</p>`;
}

function shortText(text, limit) {
  const clean = String(text || "").replace(/\s+/g, " ").trim();
  return clean.length > limit ? `${clean.slice(0, limit - 1)}...` : clean;
}

function buildQuery(params) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && String(value).trim() !== "") {
      search.set(key, String(value).trim());
    }
  });
  const query = search.toString();
  return query ? `?${query}` : "";
}

function handleCodeEditorTab(event) {
  if (event.key !== "Tab") return;

  event.preventDefault();

  const textarea = event.currentTarget;
  const indent = "    ";
  const { value, selectionStart, selectionEnd } = textarea;

  if (selectionStart !== selectionEnd && value.slice(selectionStart, selectionEnd).includes("\n")) {
    const lineStart = value.lastIndexOf("\n", selectionStart - 1) + 1;
    const selectedText = value.slice(lineStart, selectionEnd);
    const lines = selectedText.split("\n");

    if (event.shiftKey) {
      const updatedLines = lines.map((line) => {
        if (line.startsWith(indent)) return line.slice(indent.length);
        if (line.startsWith("\t")) return line.slice(1);
        const leadingSpaces = line.match(/^ {1,4}/)?.[0] || "";
        return line.slice(leadingSpaces.length);
      });
      const updatedText = updatedLines.join("\n");
      textarea.value = value.slice(0, lineStart) + updatedText + value.slice(selectionEnd);
      textarea.selectionStart = lineStart;
      textarea.selectionEnd = lineStart + updatedText.length;
      return;
    }

    const updatedText = lines.map((line) => indent + line).join("\n");
    textarea.value = value.slice(0, lineStart) + updatedText + value.slice(selectionEnd);
    textarea.selectionStart = selectionStart + indent.length;
    textarea.selectionEnd = selectionEnd + indent.length * lines.length;
    return;
  }

  if (event.shiftKey) {
    const lineStart = value.lastIndexOf("\n", selectionStart - 1) + 1;
    const beforeCursor = value.slice(lineStart, selectionStart);
    const removable = beforeCursor.match(/(?: {1,4}|\t)$/)?.[0];

    if (removable) {
      textarea.value = value.slice(0, selectionStart - removable.length) + value.slice(selectionEnd);
      textarea.selectionStart = selectionStart - removable.length;
      textarea.selectionEnd = selectionStart - removable.length;
    }
    return;
  }

  textarea.setRangeText(indent, selectionStart, selectionEnd, "end");
}

async function loadProfile() {
  state.profile = await api("/users/me");
  renderSession();
  renderProfile();
}

async function loadStats() {
  state.stats = await api("/users/me/stats");
  renderStats();
}

async function loadCourses() {
  state.courses = await api("/courses/");
  renderCourses();
  renderTaskCourseOptions();
  renderTaskCourseFilter();
}

async function loadMyCourses() {
  state.myCourses = await api("/courses/my");
  renderMyCourses();
  renderTaskCourseFilter();
}

async function loadCreatedCourses() {
  try {
    state.createdCourses = await api("/courses/my/created");
  } catch (error) {
    state.createdCourses = [];
    showToast(error.message);
  }
  renderCreatedCourses();
  renderTaskCourseFilter();
}

async function openCourse(id) {
  state.selectedCourse = await api(`/courses/${id}`);
  renderCourseDetail();
}

async function loadTasks() {
  if (!state.selectedTaskCourseId) {
    state.tasks = [];
    state.selectedTask = null;
    state.selectedTaskId = null;
    renderTasks();
    renderTaskDetail();
    return;
  }

  state.tasks = await api(`/tasks/${buildQuery({ course_id: state.selectedTaskCourseId })}`);
  if (state.selectedTaskId && !state.tasks.some((task) => String(task.id) === String(state.selectedTaskId))) {
    state.selectedTask = null;
    state.selectedTaskId = null;
    renderTaskDetail();
  }
  renderTasks();
}

async function loadUsers() {
  state.users = await api(`/users/${buildQuery({
    query: $("#userSearchQuery").value,
    group_number: $("#userSearchGroup").value,
  })}`);
  renderUsers();
}

async function loadProgressReports() {
  state.progressReports = await api(`/users/students/progress${buildQuery({
    query: $("#progressSearchQuery").value,
    group_number: $("#progressSearchGroup").value,
    student_id: $("#progressStudentId").value,
  })}`);
  renderProgressReports();
}

async function openTask(id) {
  state.selectedTask = await api(`/tasks/${id}`);
  state.selectedTaskId = state.selectedTask.id;
  const taskCourseId = state.selectedTask.course_id ? String(state.selectedTask.course_id) : "";

  if (taskCourseId && state.selectedTaskCourseId !== taskCourseId) {
    state.selectedTaskCourseId = taskCourseId;
    renderTaskCourseFilter();
  }

  if (taskCourseId && !state.tasks.some((task) => String(task.id) === String(state.selectedTaskId))) {
    state.tasks = await api(`/tasks/${buildQuery({ course_id: taskCourseId })}`);
  }

  renderTasks();
  renderTaskDetail();
}

async function loadSubmission(id) {
  const submission = await api(`/submissions/${id}`);
  state.selectedSubmissionId = submission.id;
  $("#submissionResult").textContent = JSON.stringify(submission, null, 2);
  rememberSubmission(submission);
  return submission;
}

function rememberSubmission(submission) {
  const existingIndex = state.lastSubmissions.findIndex((item) => item.id === submission.id);

  if (existingIndex >= 0) {
    state.lastSubmissions = state.lastSubmissions.map((item, index) =>
      index === existingIndex ? submission : item
    );
  } else {
    state.lastSubmissions = [submission, ...state.lastSubmissions].slice(0, 10);
  }

  localStorage.setItem("analogstepik.lastSubmissions", JSON.stringify(state.lastSubmissions));
  renderLocalSubmissions();
}

async function pollSubmission(id) {
  for (let attempt = 0; attempt < 12; attempt += 1) {
    const submission = await loadSubmission(id);
    if (submission.status && submission.status.toLowerCase() !== "pending") {
      return submission;
    }
    await new Promise((resolve) => setTimeout(resolve, 1500));
  }
  return null;
}

function switchView(name) {
  const isAdmin = Boolean(state.profile?.is_admin);
  const isTeacher = Boolean(state.profile?.is_teacher || isAdmin);

  if ((name === "teacher" || name === "progress") && !isTeacher) {
    name = "dashboard";
  }

  if ((name === "users" || name === "routes") && !isAdmin) {
    name = "dashboard";
  }

  $$(".nav-item").forEach((button) => button.classList.toggle("is-active", button.dataset.view === name));
  $$(".view").forEach((view) => view.classList.toggle("is-active", view.id === `view-${name}`));
  const [eyebrow, title] = viewMeta[name] || viewMeta.dashboard;
  $("#viewEyebrow").textContent = eyebrow;
  $("#viewTitle").textContent = title;
}

async function loadInitialData() {
  renderSession();
  try {
    await Promise.all([loadProfile(), loadStats(), loadCourses(), loadMyCourses(), loadTasks()]);
    await loadCreatedCourses();
  } catch (error) {
    showToast(error.message);
  }
}

function wireEvents() {
  $("#apiBaseAuth").addEventListener("change", (event) => setApiBase(event.target.value));
  $("#apiBaseApp").addEventListener("change", (event) => setApiBase(event.target.value));

  $$("[data-auth-tab]").forEach((button) => {
    button.addEventListener("click", () => {
      $$("[data-auth-tab]").forEach((item) => item.classList.toggle("is-active", item === button));
      $("#loginForm").classList.toggle("is-hidden", button.dataset.authTab !== "login");
      $("#registerForm").classList.toggle("is-hidden", button.dataset.authTab !== "register");
    });
  });

  $$(".nav-item").forEach((button) => {
    button.addEventListener("click", () => switchView(button.dataset.view));
  });

  $("#submissionForm textarea[name='code_text']").addEventListener("keydown", handleCodeEditorTab);

  $("#loginForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      const tokens = await api("/auth/login", {
        method: "POST",
        form: {
          username: form.get("email"),
          password: form.get("password"),
        },
        auth: false,
      });
      saveSession(tokens);
      showToast("Вход выполнен");
      await loadInitialData();
    } catch (error) {
      showToast(error.message);
    }
  });

  $("#registerForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const email = form.get("email");
    const password = form.get("password");
    try {
      await api("/auth/register", {
        method: "POST",
        body: {
          email,
          password,
        },
        auth: false,
      });

      const tokens = await api("/auth/login", {
        method: "POST",
        form: {
          username: email,
          password,
        },
        auth: false,
      });

      saveSession(tokens);
      event.currentTarget.reset();
      showToast("Аккаунт создан, вход выполнен");
      await loadInitialData();
    } catch (error) {
      showToast(error.message);
    }
  });

  $("#logoutButton").addEventListener("click", () => {
    clearSession();
    renderSession();
    showToast("Сессия завершена");
  });

  $("#profileForm").addEventListener("submit", (event) => {
    event.preventDefault();
    const submitter = event.submitter;
    const form = new FormData(event.currentTarget);
    runAction(async () => {
      state.profile = await api("/users/me", {
        method: "PUT",
        body: {
          first_name: form.get("first_name"),
          last_name: form.get("last_name"),
          group_number: form.get("group_number"),
        },
      });
      renderSession();
      renderProfile();
    }, "Профиль сохранён", submitter);
  });

  $("#refreshProfileButton").addEventListener("click", () => runAction(loadInitialData, "Данные обновлены"));
  $("#refreshTokenButton").addEventListener("click", () => runAction(refreshTokens, "Токены обновлены"));
  $("#healthButton").addEventListener("click", () => runAction(async () => {
    $("#healthResult").textContent = JSON.stringify(await api("/", { auth: false }), null, 2);
  }, "API отвечает"));

  $("#loadCoursesButton").addEventListener("click", () => runAction(loadCourses, "Курсы обновлены"));
  $("#loadMyCoursesButton").addEventListener("click", () => runAction(loadMyCourses, "Мои курсы обновлены"));
  $("#loadCreatedCoursesButton").addEventListener("click", () => runAction(loadCreatedCourses, "Курсы автора обновлены"));
  $("#loadTasksButton").addEventListener("click", () => runAction(loadTasks, "Задачи обновлены"));
  $("#taskCourseFilter").addEventListener("change", (event) => runAction(async () => {
    state.selectedTaskCourseId = event.target.value;
    state.selectedTask = null;
    state.selectedTaskId = null;
    await loadTasks();
  }, event.target.value ? "Задачи курса загружены" : ""));
  $("#loadUsersButton").addEventListener("click", () => runAction(loadUsers, "Пользователи загружены"));
  $("#loadProgressButton").addEventListener("click", () => runAction(loadProgressReports, "Прогресс загружен"));

  $("#enrollButton").addEventListener("click", () => runAction(async () => {
    if (!state.selectedCourse) throw new Error("Сначала выбери курс");
    await api(`/courses/${state.selectedCourse.id}/enroll`, { method: "POST" });
    await Promise.all([openCourse(state.selectedCourse.id), loadCourses(), loadMyCourses(), loadStats()]);
    await loadTasks();
  }, "Запись выполнена"));

  $("#unenrollButton").addEventListener("click", () => runAction(async () => {
    if (!state.selectedCourse) throw new Error("Сначала выбери курс");
    await api(`/courses/${state.selectedCourse.id}/unenroll`, { method: "POST" });
    await Promise.all([openCourse(state.selectedCourse.id), loadCourses(), loadMyCourses(), loadStats()]);
    await loadTasks();
  }, "Запись отменена"));

  $("#loadTaskByIdButton").addEventListener("click", () => runAction(async () => {
    const id = $("#taskLookupId").value;
    if (!id) throw new Error("Укажи ID задачи");
    await openTask(id);
  }, "Задача открыта"));

  $("#submissionForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    runAction(async () => {
      const submission = await api("/submissions/", {
        method: "POST",
        body: {
          task_id: Number(form.get("task_id")),
          code_text: form.get("code_text"),
          language: form.get("language"),
        },
      });
      state.selectedSubmissionId = submission.id;
      rememberSubmission(submission);
      $("#submissionLookupId").value = submission.id;
      switchView("submissions");
      $("#submissionResult").textContent = JSON.stringify(submission, null, 2);
      await pollSubmission(submission.id);
      await loadStats();
    }, "Решение отправлено");
  });

  $("#loadSubmissionButton").addEventListener("click", () => runAction(async () => {
    const id = $("#submissionLookupId").value;
    if (!id) throw new Error("Укажи ID отправки");
    await loadSubmission(id);
  }, "Отправка загружена"));

  $("#clearLocalSubmissionsButton").addEventListener("click", () => {
    state.lastSubmissions = [];
    state.selectedSubmissionId = null;
    localStorage.removeItem("analogstepik.lastSubmissions");
    renderLocalSubmissions();
  });

  $("#courseForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const submitter = event.submitter;
    const action = submitter?.dataset.courseAction || "create";
    const form = new FormData(event.currentTarget);
    const id = form.get("course_id");
    let createdCourseId = null;
    runAction(async () => {
      if (action === "delete") {
        if (!id) throw new Error("Укажи ID курса");
        await api(`/courses/${id}`, { method: "DELETE" });
      } else if (action === "update") {
        if (!id) throw new Error("Укажи ID курса");
        await api(`/courses/${id}`, {
          method: "PUT",
          body: {
            title: form.get("title"),
            description: form.get("description"),
          },
        });
      } else {
        const createdCourse = await api("/courses/", {
          method: "POST",
          body: {
            title: form.get("title"),
            description: form.get("description"),
          },
        });
        createdCourseId = createdCourse.id;
      }
      event.currentTarget.reset();
      await Promise.all([loadCourses(), loadCreatedCourses()]);
      if (createdCourseId) {
        $("#taskCourseSelect").value = String(createdCourseId);
      }
      await loadTasks();
    }, action === "delete" ? "Курс удалён" : action === "create" ? "Курс создан и выбран для задачи" : "Курс сохранён", submitter);
  });

  $("#addTestCaseButton").addEventListener("click", () => addTestCaseRow());

  $("#taskForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const submitter = event.submitter;
    const form = new FormData(event.currentTarget);
    runAction(async () => {
      const courseId = form.get("course_id");
      if (!courseId) {
        throw new Error("Выбери курс для задачи");
      }

      const testCases = [...$("#testCasesEditor").children].map((card) => ({
        input_data: card.querySelector("[data-test-input]").value,
        expected_output: card.querySelector("[data-test-output]").value,
        is_hidden: card.querySelector("[data-test-hidden]").checked,
      })).filter((test) => test.expected_output.trim());

      if (!testCases.length) throw new Error("Добавь хотя бы один тест");

      const createdTask = await api("/tasks/", {
        method: "POST",
        body: {
          title: form.get("title"),
          description: form.get("description"),
          course_id: Number(courseId),
          test_cases: testCases,
        },
      });

      event.currentTarget.reset();
      $("#testCasesEditor").innerHTML = "";
      renderTestCasesEditor();
      state.selectedTaskCourseId = String(courseId);
      renderTaskCourseFilter();
      await loadTasks();
      await openTask(createdTask.id);
      switchView("tasks");
    }, "Задача создана и открыта", submitter);
  });

  $("#loadUserButton").addEventListener("click", () => runAction(async () => {
    const id = $("#userLookupId").value;
    if (!id) throw new Error("Укажи ID пользователя");
    const profile = await api(`/users/${id}`);
    $("#userProfileResult").innerHTML = `
      <div class="meta-row">
        <span class="badge">ID ${profile.id}</span>
        <span class="badge ${profile.is_admin ? "bad" : profile.is_teacher ? "warn" : ""}">${profile.is_admin ? "admin" : profile.is_teacher ? "teacher" : "student"}</span>
      </div>
      <h3 class="detail-title">${escapeHtml(profile.email)}</h3>
      <p class="muted">${escapeHtml([profile.last_name, profile.first_name].filter(Boolean).join(" ") || "Имя не заполнено")}</p>
      <p class="muted">Группа: ${escapeHtml(profile.group_number || "-")}</p>
      <p class="muted">Курсов: ${profile.enrolled_courses?.length || 0}</p>
    `;
  }, "Пользователь найден"));

  $("#copyRoutesButton").addEventListener("click", async () => {
    const text = ROUTES.map((route) => `${route.method} ${route.path} - ${route.label}`).join("\n");
    await navigator.clipboard.writeText(text);
    showToast("Карта роутов скопирована");
  });

  document.body.addEventListener("change", (event) => {
    const progressSelect = event.target.closest("[data-progress-course-select]");

    if (progressSelect) {
      const reportIndex = Number(progressSelect.dataset.progressCourseSelect);
      const report = state.progressReports[reportIndex];
      const selectedCourse = report?.courses.find((course) => String(course.course_id) === progressSelect.value);
      const detail = document.querySelector(`[data-progress-course-detail="${reportIndex}"]`);

      if (detail) {
        detail.innerHTML = renderProgressCourseDetail(selectedCourse);
      }
    }
  });

  document.body.addEventListener("keydown", (event) => {
    const taskCard = event.target.closest("[data-open-task]");

    if (taskCard && (event.key === "Enter" || event.key === " ")) {
      event.preventDefault();
      const target = taskCard.dataset.viewTarget;
      if (target) switchView(target);
      runAction(() => openTask(taskCard.dataset.openTask), "Задача открыта");
    }
  });

  document.body.addEventListener("click", (event) => {
    const openCourseButton = event.target.closest("[data-open-course]");
    const openTaskButton = event.target.closest("[data-open-task]");
    const openSubmissionButton = event.target.closest("[data-open-submission]");
    const openUserButton = event.target.closest("[data-open-user]");
    const deleteUserButton = event.target.closest("[data-delete-user]");
    const fillCourseButton = event.target.closest("[data-fill-course]");
    const removeTestButton = event.target.closest("[data-remove-test]");

    if (openCourseButton) {
      const target = openCourseButton.dataset.viewTarget;
      if (target) switchView(target);
      runAction(() => openCourse(openCourseButton.dataset.openCourse), "Курс открыт");
    }

    if (openTaskButton) {
      const target = openTaskButton.dataset.viewTarget;
      if (target) switchView(target);
      runAction(() => openTask(openTaskButton.dataset.openTask), "Задача открыта");
    }

    if (openSubmissionButton) {
      $("#submissionLookupId").value = openSubmissionButton.dataset.openSubmission;
      runAction(() => loadSubmission(openSubmissionButton.dataset.openSubmission), "Отправка загружена");
    }

    if (openUserButton) {
      $("#userLookupId").value = openUserButton.dataset.openUser;
      runAction(async () => {
        const profile = await api(`/users/${openUserButton.dataset.openUser}`);
        $("#userProfileResult").innerHTML = `
          <div class="meta-row">
            <span class="badge">ID ${profile.id}</span>
            <span class="badge ${profile.is_admin ? "bad" : profile.is_teacher ? "warn" : ""}">${profile.is_admin ? "admin" : profile.is_teacher ? "teacher" : "student"}</span>
          </div>
          <h3 class="detail-title">${escapeHtml(profile.email)}</h3>
          <p class="muted">${escapeHtml([profile.last_name, profile.first_name].filter(Boolean).join(" ") || "Имя не заполнено")}</p>
          <p class="muted">Группа: ${escapeHtml(profile.group_number || "-")}</p>
          <p class="muted">Курсов: ${profile.enrolled_courses?.length || 0}</p>
        `;
      }, "Пользователь открыт");
    }

    if (deleteUserButton) {
      const userId = deleteUserButton.dataset.deleteUser;
      const user = state.users.find((item) => String(item.id) === String(userId));
      const label = user?.email || `ID ${userId}`;

      if (confirm(`Удалить пользователя ${label}? Это действие нельзя отменить.`)) {
        runAction(async () => {
          await api(`/users/${userId}`, { method: "DELETE" });
          state.users = state.users.filter((item) => String(item.id) !== String(userId));
          renderUsers();
        }, "Пользователь удалён", deleteUserButton);
      }
    }

    if (fillCourseButton) {
      const course = state.createdCourses.find((item) => String(item.id) === fillCourseButton.dataset.fillCourse);
      if (course) {
        const form = $("#courseForm");
        form.elements.course_id.value = course.id;
        form.elements.title.value = course.title;
        form.elements.description.value = course.description;
      }
    }

    if (removeTestButton) {
      removeTestButton.closest(".testcase-card").remove();
      if (!$("#testCasesEditor").children.length) addTestCaseRow();
    }
  });
}

function setBusy(source, busy) {
  if (!source) return;
  const form = source.closest?.("form");
  const controls = form ? [...form.querySelectorAll("button, input, textarea, select")] : [source];

  controls.forEach((control) => {
    if (busy) {
      control.dataset.wasDisabled = control.disabled ? "1" : "0";
      control.disabled = true;
    } else {
      if (control.dataset.wasDisabled === "0") {
        control.disabled = false;
      }
      delete control.dataset.wasDisabled;
    }
  });
}

async function runAction(action, successMessage, source) {
  setBusy(source, true);
  try {
    await action();
    if (successMessage) showToast(successMessage);
  } catch (error) {
    showToast(error.message);
  } finally {
    setBusy(source, false);
  }
}

function init() {
  setApiBase(state.apiBase);
  wireEvents();
  renderSession();
  renderProfile();
  renderStats();
  renderCourses();
  renderMyCourses();
  renderCreatedCourses();
  renderCourseDetail();
  renderTasks();
  renderTaskDetail();
  renderLocalSubmissions();
  renderUsers();
  renderProgressReports();
  renderRoutes();
  renderTestCasesEditor();

  if (state.accessToken) {
    loadInitialData();
  }
}

init();
