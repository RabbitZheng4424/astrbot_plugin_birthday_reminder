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

function appendMetadata(parent, label, value) {
  const row = document.createElement("div");
  row.className = "meta";
  row.textContent = `${label}：${value}`;
  parent.appendChild(row);
}

function renderItems(items) {
  listEl.replaceChildren();
  if (!items.length) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "还没有生日记录。";
    listEl.appendChild(empty);
    return;
  }

  for (const [month, rows] of groupByMonth(items)) {
    const section = document.createElement("section");
    section.className = "month-block";
    const title = document.createElement("h3");
    title.textContent = `${month} 月`;
    section.appendChild(title);

    const list = document.createElement("ul");
    for (const item of rows) {
      const row = document.createElement("li");
      row.className = "birthday-item";
      const details = document.createElement("div");
      const name = document.createElement("strong");
      name.textContent = item.display_name;
      details.appendChild(name);
      appendMetadata(details, "原始生日", item.original_birthday);
      appendMetadata(details, "下次公历", item.next_birthday_solar || "未计算");
      appendMetadata(details, "剩余天数", item.days_left ?? "-");
      if (item.aliases?.length) {
        appendMetadata(details, "别名", item.aliases.join("、"));
      }
      if (item.note) {
        appendMetadata(details, "备注", item.note);
      }

      const deleteButton = document.createElement("button");
      deleteButton.type = "button";
      deleteButton.dataset.id = item.id;
      deleteButton.dataset.name = item.display_name;
      deleteButton.className = "danger";
      deleteButton.textContent = "删除";
      row.append(details, deleteButton);
      list.appendChild(row);
    }
    section.appendChild(list);
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
  const submitButton = form.querySelector('button[type="submit"]');
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
    submitButton.disabled = true;
    const result = await bridge.apiPost("birthdays/add", payload);
    setStatus(result.message || "已保存生日记录");
    form.reset();
    document.getElementById("calendar-type").value = "solar";
    await loadItems();
  } catch (error) {
    setStatus(error.message || String(error), true);
  } finally {
    submitButton.disabled = false;
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
  if (!window.confirm(`确定删除 ${button.dataset.name || "这条记录"} 的生日吗？`)) {
    return;
  }
  try {
    button.disabled = true;
    const result = await bridge.apiPost("birthdays/delete", { id: button.dataset.id });
    setStatus(result.message || "已删除生日记录");
    await loadItems();
  } catch (error) {
    button.disabled = false;
    setStatus(error.message || String(error), true);
  }
});

await bridge.ready();
await loadItems();
