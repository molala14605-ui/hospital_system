const API = "/api/v1";

function token() {
  return localStorage.getItem("token") || "";
}

function setMsg(id, text, ok) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = text || "";
  el.classList.toggle("ok", !!ok);
  if (id === "authMsg") {
    el.style.display = text ? "flex" : "none";
  }
}

async function api(path, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  const t = token();
  if (t) headers["Authorization"] = "Bearer " + t;
  if (opts.body && typeof opts.body === "object" && !(opts.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(opts.body);
  }
  const r = await fetch(API + path, { ...opts, headers });
  const text = await r.text();
  let data;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!r.ok) {
    const detail = data && data.detail ? (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)) : text;
    throw new Error(detail || r.statusText);
  }
  return data;
}

function roleLabelAr(role) {
  if (role === "admin") return "مدير النظام";
  if (role === "doctor") return "طبيب";
  if (role === "patient") return "مريض";
  return role;
}

function localDateTimeToIso(value) {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "";
  return d.toISOString();
}

let adminApptPage = 1;
let doctorApptPage = 1;
let patientApptPage = 1;

function appointmentsListUrl(doc, pat, page, pageSize = 8) {
  const p = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (doc) p.append("doctor_id", String(doc));
  if (pat) p.append("patient_id", String(pat));
  return "/appointments?" + p.toString();
}

function renderApptPager(containerId, data, onPage) {
  const el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = "";
  if (!data.total_pages || data.total_pages <= 1) return;
  const wrap = document.createElement("div");
  wrap.className = "pager-inner";
  const meta = document.createElement("span");
  meta.className = "pager-meta";
  meta.textContent = `صفحة ${data.page} من ${data.total_pages} — ${data.total} موعد`;
  wrap.appendChild(meta);
  const row = document.createElement("div");
  row.className = "pager-btns";
  if (data.page > 1) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "btn-ghost";
    b.textContent = "السابق";
    b.addEventListener("click", () => onPage(data.page - 1));
    row.appendChild(b);
  }
  if (data.page < data.total_pages) {
    const b2 = document.createElement("button");
    b2.type = "button";
    b2.className = "btn-ghost";
    b2.textContent = "التالي";
    b2.addEventListener("click", () => onPage(data.page + 1));
    row.appendChild(b2);
  }
  wrap.appendChild(row);
  el.appendChild(wrap);
}

function setGuestScreen(mode) {
  document.getElementById("guestView").setAttribute("data-guest-screen", mode);
}

function showLanding() {
  setMsg("authMsg", "");
  setGuestScreen("landing");
}

function showLoginScreen() {
  setMsg("authMsg", "");
  setGuestScreen("login");
}

function showRegisterScreen() {
  setMsg("authMsg", "");
  setGuestScreen("register");
}

function showGuest() {
  document.getElementById("guestView").classList.remove("hidden");
  document.getElementById("appView").classList.add("hidden");
  showLanding();
}

function showRolePanels(role) {
  document.getElementById("panelAdmin").classList.add("hidden");
  document.getElementById("panelDoctor").classList.add("hidden");
  document.getElementById("panelPatient").classList.add("hidden");
  if (role === "admin") document.getElementById("panelAdmin").classList.remove("hidden");
  if (role === "doctor") document.getElementById("panelDoctor").classList.remove("hidden");
  if (role === "patient") document.getElementById("panelPatient").classList.remove("hidden");
}

async function enterApp() {
  const me = await api("/auth/me");
  document.getElementById("guestView").classList.add("hidden");
  document.getElementById("appView").classList.remove("hidden");
  document.getElementById("userChip").textContent = me.full_name;
  document.getElementById("roleBadge").textContent = roleLabelAr(me.role);
  showRolePanels(me.role);

  if (me.role === "admin") {
    await loadAdminDoctors();
    await loadAdminPatients();
    await loadAdminAppts(1);
  }
  if (me.role === "doctor") {
    await loadDoctorAppts(1);
  }
  if (me.role === "patient") {
    await loadPatDoctorsSelect();
    await loadPatientAppts(1);
    await loadPatientProfile();
  }
  return me;
}

function leaveApp() {
  localStorage.removeItem("token");
  showGuest();
}

document.getElementById("btnGoLogin").addEventListener("click", () => showLoginScreen());
document.getElementById("btnGoRegister").addEventListener("click", () => showRegisterScreen());
document.getElementById("btnBackLandingFromLogin").addEventListener("click", () => showLanding());
document.getElementById("btnBackLandingFromRegister").addEventListener("click", () => showLanding());

document.getElementById("btnLogin").addEventListener("click", async () => {
  setMsg("authMsg", "");
  const email = document.getElementById("loginEmail").value.trim();
  const password = document.getElementById("loginPass").value;
  if (!email || !password) {
    setMsg("authMsg", "أدخل البريد وكلمة المرور");
    return;
  }
  try {
    const data = await api("/auth/login", { method: "POST", body: { email, password } });
    localStorage.setItem("token", data.access_token);
    await enterApp();
    setMsg("authMsg", "");
  } catch (e) {
    setMsg("authMsg", e.message);
  }
});

document.getElementById("btnRegister").addEventListener("click", async () => {
  setMsg("authMsg", "");
  const email = document.getElementById("regEmail").value.trim();
  const full_name = document.getElementById("regName").value.trim();
  const password = document.getElementById("regPass").value;
  if (!email || !full_name || !password) {
    setMsg("authMsg", "أكمل جميع الحقول");
    return;
  }
  try {
    await api("/auth/register", { method: "POST", body: { email, full_name, password } });
    const data = await api("/auth/login", { method: "POST", body: { email, password } });
    localStorage.setItem("token", data.access_token);
    await enterApp();
    setMsg("authMsg", "");
  } catch (e) {
    setMsg("authMsg", e.message);
  }
});

document.getElementById("btnLogout").addEventListener("click", () => leaveApp());

/* ——— Admin ——— */
async function loadAdminDoctors() {
  const wrap = document.getElementById("adminDoctorsTable");
  wrap.textContent = "جاري التحميل…";
  try {
    const rows = await api("/doctors");
    wrap.innerHTML = "";
    const table = document.createElement("table");
    table.className = "data";
    const thead = document.createElement("thead");
    thead.innerHTML = "<tr><th>#</th><th>الاسم</th><th>البريد</th><th>التخصص</th><th>القسم</th><th></th></tr>";
    const tbody = document.createElement("tbody");
    for (const r of rows) {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${r.id}</td><td></td><td></td><td></td><td></td><td class="actions-cell"></td>`;
      tr.cells[1].textContent = r.full_name || "";
      tr.cells[2].textContent = r.email || "";
      tr.cells[3].textContent = r.specialization || "";
      tr.cells[4].textContent = r.department || "";
      const del = document.createElement("button");
      del.className = "btn-danger";
      del.textContent = "حذف";
      del.addEventListener("click", async () => {
        if (!confirm("حذف هذا الطبيب؟")) return;
        try {
          await api(`/doctors/${r.id}`, { method: "DELETE" });
          await loadAdminDoctors();
        } catch (e) {
          alert(e.message);
        }
      });
      tr.cells[5].appendChild(del);
      tbody.appendChild(tr);
    }
    table.appendChild(thead);
    table.appendChild(tbody);
    wrap.appendChild(table);
  } catch (e) {
    wrap.textContent = e.message;
  }
}

async function loadAdminPatients() {
  const wrap = document.getElementById("adminPatientsTable");
  wrap.textContent = "جاري التحميل…";
  try {
    const rows = await api("/patients");
    wrap.innerHTML = "";
    const table = document.createElement("table");
    table.className = "data";
    const thead = document.createElement("thead");
    thead.innerHTML = "<tr><th>#</th><th>الاسم</th><th>البريد</th><th>الهاتف</th><th></th></tr>";
    const tbody = document.createElement("tbody");
    for (const r of rows) {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${r.id}</td><td></td><td></td><td></td><td class="actions-cell"></td>`;
      tr.cells[1].textContent = r.full_name || "";
      tr.cells[2].textContent = r.email || "";
      tr.cells[3].textContent = r.phone || "";
      const del = document.createElement("button");
      del.className = "btn-danger";
      del.textContent = "حذف";
      del.addEventListener("click", async () => {
        if (!confirm("حذف هذا المريض؟")) return;
        try {
          await api(`/patients/${r.id}`, { method: "DELETE" });
          await loadAdminPatients();
        } catch (e) {
          alert(e.message);
        }
      });
      tr.cells[4].appendChild(del);
      tbody.appendChild(tr);
    }
    table.appendChild(thead);
    table.appendChild(tbody);
    wrap.appendChild(table);
  } catch (e) {
    wrap.textContent = e.message;
  }
}

async function loadAdminAppts(page) {
  if (page == null || page < 1) page = 1;
  adminApptPage = page;
  const wrap = document.getElementById("adminApptsTable");
  const pager = document.getElementById("adminApptPager");
  wrap.textContent = "جاري التحميل…";
  if (pager) pager.innerHTML = "";
  const doc = document.getElementById("admApptDoc").value.trim();
  const pat = document.getElementById("admApptPat").value.trim();
  try {
    const data = await api(appointmentsListUrl(doc || null, pat || null, page, 8));
    const rows = data.items || [];
    wrap.innerHTML = "";
    renderApptPager("adminApptPager", data, (p) => loadAdminAppts(p));
    if (!rows.length) {
      wrap.textContent = "لا توجد مواعيد في هذه الصفحة.";
      return;
    }
    const table = document.createElement("table");
    table.className = "data";
    const thead = document.createElement("thead");
    thead.innerHTML =
      "<tr><th>#</th><th>طبيب</th><th>مريض</th><th>البداية</th><th>النهاية</th><th>الحالة</th><th></th></tr>";
    const tbody = document.createElement("tbody");
    for (const r of rows) {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${r.id}</td><td>${r.doctor_id}</td><td>${r.patient_id}</td><td></td><td></td><td></td><td class="actions-cell"></td>`;
      tr.cells[3].textContent = r.start_time || "";
      tr.cells[4].textContent = r.end_time || "";
      tr.cells[5].textContent = r.status || "";
      const del = document.createElement("button");
      del.className = "btn-danger";
      del.textContent = "حذف";
      del.addEventListener("click", async () => {
        if (!confirm("حذف هذا الموعد؟")) return;
        try {
          await api(`/appointments/${r.id}`, { method: "DELETE" });
          await loadAdminAppts(adminApptPage);
        } catch (e) {
          alert(e.message);
        }
      });
      tr.cells[6].appendChild(del);
      tbody.appendChild(tr);
    }
    table.appendChild(thead);
    table.appendChild(tbody);
    wrap.appendChild(table);
  } catch (e) {
    wrap.textContent = e.message;
  }
}

document.getElementById("btnAdminCreateDoctor").addEventListener("click", async () => {
  setMsg("admDocMsg", "");
  const body = {
    email: document.getElementById("admDocEmail").value.trim(),
    password: document.getElementById("admDocPass").value,
    full_name: document.getElementById("admDocName").value.trim(),
    specialization: document.getElementById("admDocSpec").value.trim(),
    department: document.getElementById("admDocDept").value.trim() || null,
  };
  try {
    await api("/doctors", { method: "POST", body });
    setMsg("admDocMsg", "تم حفظ الطبيب", true);
    await loadAdminDoctors();
  } catch (e) {
    setMsg("admDocMsg", e.message);
  }
});

document.getElementById("btnAdminCreatePatient").addEventListener("click", async () => {
  setMsg("admPatMsg", "");
  const body = {
    email: document.getElementById("admPatEmail").value.trim(),
    password: document.getElementById("admPatPass").value,
    full_name: document.getElementById("admPatName").value.trim(),
    phone: document.getElementById("admPatPhone").value.trim() || null,
    medical_notes: null,
  };
  try {
    await api("/patients", { method: "POST", body });
    setMsg("admPatMsg", "تم حفظ المريض", true);
    await loadAdminPatients();
  } catch (e) {
    setMsg("admPatMsg", e.message);
  }
});

document.getElementById("btnAdminLoadDoctors").addEventListener("click", () => loadAdminDoctors());
document.getElementById("btnAdminLoadPatients").addEventListener("click", () => loadAdminPatients());
document.getElementById("btnAdminLoadAppts").addEventListener("click", () => loadAdminAppts(1));

/* ——— Doctor ——— */
async function loadDoctorAppts(page) {
  if (page == null || page < 1) page = 1;
  doctorApptPage = page;
  const wrap = document.getElementById("doctorApptsTable");
  const pager = document.getElementById("doctorApptPager");
  setMsg("doctorMsg", "");
  wrap.textContent = "جاري التحميل…";
  if (pager) pager.innerHTML = "";
  try {
    const data = await api(appointmentsListUrl(null, null, page, 8));
    const rows = data.items || [];
    wrap.innerHTML = "";
    renderApptPager("doctorApptPager", data, (p) => loadDoctorAppts(p));
    if (!rows.length) {
      wrap.textContent = "لا توجد مواعيد.";
      return;
    }
    const table = document.createElement("table");
    table.className = "data";
    const thead = document.createElement("thead");
    thead.innerHTML =
      "<tr><th>#</th><th>مريض</th><th>البداية</th><th>النهاية</th><th>الحالة</th><th>إجراءات</th></tr>";
    const tbody = document.createElement("tbody");
    for (const r of rows) {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${r.id}</td><td>${r.patient_id}</td><td></td><td></td><td></td><td class="actions-cell"></td>`;
      tr.cells[2].textContent = r.start_time || "";
      tr.cells[3].textContent = r.end_time || "";
      tr.cells[4].textContent = r.status || "";
      const cell = tr.cells[5];
      if (r.status === "scheduled") {
        const b1 = document.createElement("button");
        b1.className = "btn-ghost";
        b1.textContent = "مكتمل";
        b1.addEventListener("click", async () => {
          try {
            await api(`/appointments/${r.id}/status`, { method: "PUT", body: { status: "completed" } });
            await loadDoctorAppts(doctorApptPage);
          } catch (e) {
            setMsg("doctorMsg", e.message);
          }
        });
        const b2 = document.createElement("button");
        b2.className = "btn-ghost";
        b2.textContent = "إلغاء";
        b2.addEventListener("click", async () => {
          try {
            await api(`/appointments/${r.id}/status`, { method: "PUT", body: { status: "cancelled" } });
            await loadDoctorAppts(doctorApptPage);
          } catch (e) {
            setMsg("doctorMsg", e.message);
          }
        });
        cell.appendChild(b1);
        cell.appendChild(b2);
      } else {
        cell.textContent = "—";
      }
      tbody.appendChild(tr);
    }
    table.appendChild(thead);
    table.appendChild(tbody);
    wrap.appendChild(table);
  } catch (e) {
    wrap.textContent = e.message;
  }
}

document.getElementById("btnDoctorRefresh").addEventListener("click", () => loadDoctorAppts(1));

/* ——— Patient ——— */
let patientSelfId = null;

async function loadPatDoctorsSelect() {
  const sel = document.getElementById("patDoctorSelect");
  sel.innerHTML = '<option value="">— اختر طبيباً —</option>';
  try {
    const rows = await api("/doctors");
    for (const r of rows) {
      const opt = document.createElement("option");
      opt.value = String(r.id);
      opt.textContent = `${r.full_name || r.email} (#${r.id}) — ${r.specialization || ""}`;
      sel.appendChild(opt);
    }
  } catch {
    /* ignore if not logged in yet */
  }
}

document.getElementById("btnPatLoadDoctors").addEventListener("click", async () => {
  setMsg("patBookMsg", "");
  try {
    await loadPatDoctorsSelect();
    setMsg("patBookMsg", "تم تحديث قائمة الأطباء", true);
  } catch (e) {
    setMsg("patBookMsg", e.message);
  }
});

document.getElementById("btnPatBook").addEventListener("click", async () => {
  setMsg("patBookMsg", "");
  const doctor_id = Number(document.getElementById("patDoctorSelect").value);
  const start_time = localDateTimeToIso(document.getElementById("patStart").value);
  const end_time = localDateTimeToIso(document.getElementById("patEnd").value);
  const reason = document.getElementById("patReason").value.trim() || null;
  if (!doctor_id || !start_time || !end_time) {
    setMsg("patBookMsg", "اختر طبيباً وأوقات البداية والنهاية");
    return;
  }
  try {
    await api("/appointments", { method: "POST", body: { doctor_id, start_time, end_time, reason } });
    setMsg("patBookMsg", "تم الحجز", true);
    await loadPatientAppts(1);
  } catch (e) {
    setMsg("patBookMsg", e.message);
  }
});

async function loadPatientAppts(page) {
  if (page == null || page < 1) page = 1;
  patientApptPage = page;
  const wrap = document.getElementById("patientApptsTable");
  const pager = document.getElementById("patientApptPager");
  setMsg("patApptMsg", "");
  wrap.textContent = "جاري التحميل…";
  if (pager) pager.innerHTML = "";
  try {
    const data = await api(appointmentsListUrl(null, null, page, 8));
    const rows = data.items || [];
    wrap.innerHTML = "";
    renderApptPager("patientApptPager", data, (p) => loadPatientAppts(p));
    if (!rows.length) {
      wrap.textContent = "لا توجد مواعيد.";
      return;
    }
    const table = document.createElement("table");
    table.className = "data";
    const thead = document.createElement("thead");
    thead.innerHTML =
      "<tr><th>#</th><th>طبيب</th><th>البداية</th><th>النهاية</th><th>الحالة</th><th></th></tr>";
    const tbody = document.createElement("tbody");
    for (const r of rows) {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${r.id}</td><td>${r.doctor_id}</td><td></td><td></td><td></td><td class="actions-cell"></td>`;
      tr.cells[2].textContent = r.start_time || "";
      tr.cells[3].textContent = r.end_time || "";
      tr.cells[4].textContent = r.status || "";
      const cell = tr.cells[5];
      if (r.status === "scheduled") {
        const b = document.createElement("button");
        b.className = "btn-danger";
        b.textContent = "إلغاء";
        b.addEventListener("click", async () => {
          if (!confirm("إلغاء هذا الموعد؟")) return;
          try {
            await api(`/appointments/${r.id}/status`, { method: "PUT", body: { status: "cancelled" } });
            await loadPatientAppts(patientApptPage);
          } catch (e) {
            setMsg("patApptMsg", e.message);
          }
        });
        cell.appendChild(b);
      } else {
        cell.textContent = "—";
      }
      tbody.appendChild(tr);
    }
    table.appendChild(thead);
    table.appendChild(tbody);
    wrap.appendChild(table);
  } catch (e) {
    wrap.textContent = e.message;
  }
}

document.getElementById("btnPatRefreshAppts").addEventListener("click", () => loadPatientAppts(1));

async function loadPatientProfile() {
  setMsg("patProfileMsg", "");
  try {
    const p = await api("/patients/me");
    patientSelfId = p.id;
    document.getElementById("patPhoneEdit").value = p.phone || "";
    document.getElementById("patProfileHint").textContent = `رقم الملف: ${p.id} — يمكنك تعديل الهاتف فقط.`;
  } catch (e) {
    document.getElementById("patProfileHint").textContent = e.message;
  }
}

document.getElementById("btnPatSaveProfile").addEventListener("click", async () => {
  setMsg("patProfileMsg", "");
  if (!patientSelfId) {
    setMsg("patProfileMsg", "تعذر تحديد الملف");
    return;
  }
  try {
    await api(`/patients/${patientSelfId}`, {
      method: "PUT",
      body: { phone: document.getElementById("patPhoneEdit").value.trim() || null },
    });
    setMsg("patProfileMsg", "تم الحفظ", true);
  } catch (e) {
    setMsg("patProfileMsg", e.message);
  }
});

document.getElementById("btnPatReschedule").addEventListener("click", async () => {
  setMsg("patRsMsg", "");
  const id = Number(document.getElementById("patRsId").value);
  const st = localDateTimeToIso(document.getElementById("patRsStart").value);
  const en = localDateTimeToIso(document.getElementById("patRsEnd").value);
  if (!id || !st || !en) {
    setMsg("patRsMsg", "أكمل الحقول");
    return;
  }
  try {
    await api(`/appointments/${id}`, { method: "PUT", body: { start_time: st, end_time: en } });
    setMsg("patRsMsg", "تم التحديث", true);
    await loadPatientAppts(patientApptPage);
  } catch (e) {
    setMsg("patRsMsg", e.message);
  }
});

document.getElementById("btnDocReschedule").addEventListener("click", async () => {
  setMsg("docRsMsg", "");
  const id = Number(document.getElementById("docRsId").value);
  const st = localDateTimeToIso(document.getElementById("docRsStart").value);
  const en = localDateTimeToIso(document.getElementById("docRsEnd").value);
  if (!id || !st || !en) {
    setMsg("docRsMsg", "أكمل الحقول");
    return;
  }
  try {
    await api(`/appointments/${id}`, { method: "PUT", body: { start_time: st, end_time: en } });
    setMsg("docRsMsg", "تم التحديث", true);
    await loadDoctorAppts(doctorApptPage);
  } catch (e) {
    setMsg("docRsMsg", e.message);
  }
});

document.getElementById("btnAdmReschedule").addEventListener("click", async () => {
  setMsg("admRsMsg", "");
  const id = Number(document.getElementById("admRsId").value);
  const st = localDateTimeToIso(document.getElementById("admRsStart").value);
  const en = localDateTimeToIso(document.getElementById("admRsEnd").value);
  const docRaw = document.getElementById("admRsDoc").value.trim();
  const doctor_id = docRaw ? Number(docRaw) : null;
  if (!id || !st || !en) {
    setMsg("admRsMsg", "أكمل الحقول");
    return;
  }
  const body = { start_time: st, end_time: en };
  if (doctor_id) body.doctor_id = doctor_id;
  try {
    await api(`/appointments/${id}`, { method: "PUT", body });
    setMsg("admRsMsg", "تم التحديث", true);
    await loadAdminAppts(adminApptPage);
  } catch (e) {
    setMsg("admRsMsg", e.message);
  }
});

/* ——— Boot ——— */
(async function init() {
  if (token()) {
    try {
      await enterApp();
    } catch {
      leaveApp();
    }
  }
})();
