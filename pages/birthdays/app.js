const bridge = window.AstrBotPluginPage;
const statusEl = document.getElementById("status");
const listEl = document.getElementById("birthday-list");
const versionEl = document.getElementById("version");
const form = document.getElementById("birthday-form");

function setStatus(text, isError = false) {
  statusEl.textContent = text || "";
  statusEl.dataset.error = isError ? "true" : "false";
}

function groupByMonth(items) {
  const groups = new Map();
  for (const item of items) {
    const month = Number(item.birth_month || 0);
    if (!groups.has(month)) {
      groups.set(month, []);
    }
    groups.get(month).push(item);
  }
  return [...groups.entries()].sort((a, b) => a[0] - b[0]);
}

function renderItems(items) {
  listEl.innerHTML = "";
  if (!items.length) {
    listEl.innerHTML = '<p class="empty">还没有生日记录。</p>';
    return;
  }
  for (const [month, rows] of groupByMonth(items)) {
    const section = document.createElement("section");
    section.className = "month-block";
    const title = document.createElement("h3");
    title.textContent = `${month} 月`;
    section.appendChild(title);

    const ul = document.createElement("ul");
    for (const item of rows) {
      const li = document.createElement("li");
      li.className = "birthday-item";
      li.innerHTML = `
        <div>
          <strong>${item.display_name}</strong>
          <div class="meta">原始生日：${item.original_birthday}</div>
          <div class="meta">下次公历：${item.next_birthday_solar || "未计算"}</div>
          <div class="meta">剩余天数：${item.days_left ?? "-"}</div>
          ${item.aliases?.length ? `<div class="meta">别名：${item.aliases.join("、")}</div>` : ""}
          ${item.note ? `<div class="meta">备注：${item.note}</div>` : ""}
        </div>
        <button data-id="${item.id}" class="danger">删除</button>
      `;
      ul.appendChild(li);
    }
    section.appendChild(ul);
    listEl.appendChild(section);
  }
}

async function loadItems() {
  try {
    const data = await bridge.apiGet("birthdays");
    versionEl.textContent = `版本 ${data.pluginVersion}`;
    renderItems(data.items || []);
    setStatus("已刷新生日列表");
  } catch (error) {
    setStatus(error.message || String(error), true);
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = {
    name: document.getElementById("name").value.trim(),
    birthday: document.getElementById("birthday").value.trim(),
    calendar_type: document.getElementById("calendar-type").value,
    aliases: document.getElementById("aliases").value
      .split(/[,，、]/)
      .map((item) => item.trim())
      .filter(Boolean),
    note: document.getElementById("note").value.trim(),
  };
  try {
    const result = await bridge.apiPost("birthdays/add", payload);
    setStatus(result.message || "已保存生日记录");
    form.reset();
    document.getElementById("calendar-type").value = "solar";
    await loadItems();
  } catch (error) {
    setStatus(error.message || String(error), true);
  }
});

document.getElementById("refresh-list").addEventListener("click", loadItems);

document.getElementById("refresh-solar").addEventListener("click", async () => {
  try {
    const result = await bridge.apiPost("birthdays/refresh", {});
    setStatus(result.message || "已刷新下一次公历生日");
    await loadItems();
  } catch (error) {
    setStatus(error.message || String(error), true);
  }
});

listEl.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-id]");
  if (!button) {
    return;
  }
  const id = button.dataset.id;
  try {
    const result = await bridge.apiPost("birthdays/delete", { id });
    setStatus(result.message || "已删除生日记录");
    await loadItems();
  } catch (error) {
    setStatus(error.message || String(error), true);
  }
});

await bridge.ready();
await loadItems();
