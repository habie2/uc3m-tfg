let allFiles = [];
let folderTree = {};
let currentFolder = null;
let selectedFiles = new Set();
let viewMode = "grid";
let sortMode = "name";
let searchQuery = "";
let extensionFilters = new Set();

const extIcons = {
  pdf: "📄",
  doc: "📝",
  docx: "📝",
  xls: "📊",
  xlsx: "📊",
  ppt: "📑",
  pptx: "📑",
  txt: "📃",
  md: "📃",
  jpg: "🖼",
  jpeg: "🖼",
  png: "🖼",
  gif: "🖼",
  webp: "🖼",
  svg: "🖼",
  mp4: "🎬",
  avi: "🎬",
  mov: "🎬",
  mkv: "🎬",
  mp3: "🎵",
  wav: "🎵",
  flac: "🎵",
  zip: "🗜",
  rar: "🗜",
  gz: "🗜",
  tar: "🗜",
  js: "⚙️",
  ts: "⚙️",
  py: "⚙️",
  java: "⚙️",
  html: "🌐",
  css: "🎨",
  json: "📋",
  xml: "📋",
  csv: "📋",
};

function getIcon(name) {
  const ext = name.split(".").pop().toLowerCase();
  return extIcons[ext] || "📄";
}

function formatDate(ts) {
  if (!ts) return "";
  const d = new Date(ts);
  return d.toLocaleDateString("es-ES", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

// Ahora soporta archivos sin ruta (móvil o archivos sueltos)
function buildTree(files) {
  const tree = {};
  files.forEach((f) => {
    // Si no tiene ruta relativa (archivos seleccionados directamente o desde móvil)
    if (!f.webkitRelativePath) {
      if (!tree["Archivos Sueltos"])
        tree["Archivos Sueltos"] = { __children: {}, __files: [] };
      tree["Archivos Sueltos"].__files.push(f);
      return;
    }

    const parts = f.webkitRelativePath.split("/");
    // Si están en la raíz de la carpeta seleccionada
    if (parts.length < 2) {
      if (!tree["Raíz"]) tree["Raíz"] = { __children: {}, __files: [] };
      tree["Raíz"].__files.push(f);
      return;
    }

    let node = tree;
    for (let i = 0; i < parts.length - 1; i++) {
      const p = parts[i];
      if (!node[p]) node[p] = { __children: {}, __files: [] };
      if (i === parts.length - 2) node[p].__files.push(f);
      node = node[p].__children;
    }
  });
  return tree;
}

function countFiles(node) {
  let count = node.__files ? node.__files.length : 0;
  if (node.__children) {
    Object.values(node.__children).forEach((child) => {
      count += countFiles(child);
    });
  }
  return count;
}

function getAllFilesFlat(node) {
  let files = [...(node.__files || [])];
  Object.values(node.__children || {}).forEach((child) => {
    files = files.concat(getAllFilesFlat(child));
  });
  return files;
}

function renderTree(nodeObj, parentEl, depth, pathPrefix) {
  Object.entries(nodeObj).forEach(([name, node]) => {
    if (name.startsWith("__")) return;
    const path = pathPrefix ? pathPrefix + "/" + name : name;
    const total = countFiles(node);
    const hasChildren = Object.keys(node.__children || {}).some(
      (k) => !k.startsWith("__"),
    );

    const item = document.createElement("div");
    item.className = "tree-item";
    item.style.paddingLeft = 12 + depth * 16 + "px";

    const toggle = document.createElement("span");
    toggle.className = "toggle-btn";
    toggle.textContent = hasChildren ? "▶" : "";

    const icon = document.createElement("span");
    icon.className = "icon";
    icon.textContent = name === "Archivos Sueltos" ? "📄" : "📁";

    const nameEl = document.createElement("span");
    nameEl.className = "name";
    nameEl.textContent = name;

    const badge = document.createElement("span");
    badge.className = "count";
    badge.textContent = total;

    item.append(toggle, icon, nameEl, badge);

    let expanded = false;
    let childContainer = null;

    if (hasChildren) {
      childContainer = document.createElement("div");
      childContainer.style.display = "none";
      renderTree(node.__children, childContainer, depth + 1, path);
    }

    item.addEventListener("click", (e) => {
      e.stopPropagation();
      document
        .querySelectorAll(".tree-item.active")
        .forEach((el) => el.classList.remove("active"));
      item.classList.add("active");
      navigateTo(node, path);
      if (hasChildren) {
        expanded = !expanded;
        childContainer.style.display = expanded ? "block" : "none";
        toggle.style.transform = expanded ? "rotate(90deg)" : "";
      }
    });

    parentEl.appendChild(item);
    if (hasChildren) parentEl.appendChild(childContainer);
  });
}

function navigateTo(node, path) {
  currentFolder = { node, path };
  selectedFiles.clear();
  document.getElementById("open-btn").disabled = true;
  renderBreadcrumb(path);
  renderContent();
}

function renderBreadcrumb(path) {
  const bc = document.getElementById("breadcrumb");
  bc.innerHTML = "";
  path.split("/").forEach((p, i, arr) => {
    const span = document.createElement("span");
    span.className = "bc-part";
    span.textContent = p;
    bc.appendChild(span);
    if (i < arr.length - 1) {
      const sep = document.createElement("span");
      sep.className = "bc-sep";
      sep.textContent = " / ";
      bc.appendChild(sep);
    }
  });
}

function getVisibleFiles() {
  if (!currentFolder) return [];
  let files = getAllFilesFlat(currentFolder.node);

  // Filtro por búsqueda
  if (searchQuery) {
    const q = searchQuery.toLowerCase();
    files = files.filter((f) => f.name.toLowerCase().includes(q));
  }

  // Filtro múltiple por extensión
  if (extensionFilters.size > 0) {
    files = files.filter((f) => {
      const ext = f.name.includes(".")
        ? f.name.split(".").pop().toLowerCase()
        : "";
      return extensionFilters.has(ext);
    });
  }

  // Ordenamiento
  return [...files].sort((a, b) => {
    if (sortMode === "name") return a.name.localeCompare(b.name);
    if (sortMode === "date")
      return (b.lastModified || 0) - (a.lastModified || 0);
    if (sortMode === "type") {
      const ea = a.name.split(".").pop().toLowerCase();
      const eb = b.name.split(".").pop().toLowerCase();
      return ea.localeCompare(eb) || a.name.localeCompare(b.name);
    }
    return 0;
  });
}

function getRelPath(f) {
  if (!f.webkitRelativePath) return f.name;
  const parts = f.webkitRelativePath.split("/");
  const base = currentFolder.path.split("/");
  return parts.slice(base.length).join(" / ");
}

function renderContent() {
  const content = document.getElementById("content");
  const files = getVisibleFiles();
  content.className = viewMode === "grid" ? "grid-view" : "list-view";
  content.innerHTML = "";

  if (!files.length) {
    content.innerHTML =
      '<div class="empty-state"><div class="empty-icon">🔍</div><span>No hay archivos que coincidan</span></div>';
    document.getElementById("status-left").textContent = "Sin archivos";
    document.getElementById("status-right").textContent = "";
    return;
  }

  files.forEach((f) => {
    const key = f._id; // Usamos un ID seguro en caso de archivos sin ruta
    if (viewMode === "grid") {
      const card = document.createElement("div");
      card.className =
        "file-card" + (selectedFiles.has(key) ? " selected" : "");
      card.innerHTML = `<div class="file-icon">${getIcon(f.name)}</div><div class="file-name">${f.name}</div><div class="file-date">${formatDate(f.lastModified)}</div>`;
      card.addEventListener("click", (e) => toggleSelect(key, card, e));
      card.addEventListener("dblclick", () => openFile(f));
      content.appendChild(card);
    } else {
      const row = document.createElement("div");
      row.className = "file-row" + (selectedFiles.has(key) ? " selected" : "");
      const ext = f.name.includes(".")
        ? f.name.split(".").pop().toUpperCase()
        : "—";
      row.innerHTML = `<span class="file-icon">${getIcon(f.name)}</span><span class="file-name">${getRelPath(f)}</span><span class="file-date">${formatDate(f.lastModified)}</span><span class="file-type">${ext}</span>`;
      row.addEventListener("click", (e) => toggleSelect(key, row, e));
      row.addEventListener("dblclick", () => openFile(f));
      content.appendChild(row);
    }
  });

  document.getElementById("status-left").textContent =
    `${files.length} archivo(s)`;
}

function toggleSelect(key, el, e) {
  e.stopPropagation(); // Evita que el clic llegue al fondo y deseleccione todo

  if (!e.ctrlKey && !e.metaKey) {
    selectedFiles.clear();
    document
      .querySelectorAll(".file-card.selected, .file-row.selected")
      .forEach((x) => x.classList.remove("selected"));
  }
  if (selectedFiles.has(key)) {
    selectedFiles.delete(key);
    el.classList.remove("selected");
  } else {
    selectedFiles.add(key);
    el.classList.add("selected");
  }
  document.getElementById("open-btn").disabled = selectedFiles.size === 0;
  document.getElementById("status-right").textContent =
    selectedFiles.size > 0 ? `${selectedFiles.size} seleccionado(s)` : "";
}

// Deseleccionar al hacer clic en el fondo vacío del panel de archivos
document.getElementById("content").addEventListener("click", (e) => {
  if (
    e.target.id === "content" ||
    e.target.classList.contains("empty-state") ||
    e.target.classList.contains("grid-view") ||
    e.target.classList.contains("list-view")
  ) {
    selectedFiles.clear();
    document
      .querySelectorAll(".file-card.selected, .file-row.selected")
      .forEach((x) => x.classList.remove("selected"));
    document.getElementById("open-btn").disabled = true;
    document.getElementById("status-right").textContent = "";
  }
});

function openFile(f) {
  const url = URL.createObjectURL(f);
  window.open(url, "_blank");
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}

function openSelected() {
  const files = getVisibleFiles();
  const keys = selectedFiles;
  files.filter((f) => keys.has(f._id)).forEach(openFile);
}

function filterFiles(q) {
  searchQuery = q;
  renderContent();
}
function sortFiles(mode) {
  sortMode = mode;
  renderContent();
}

// NUEVO: Funciones para el menú desplegable de extensiones
function toggleExtMenu(e) {
  e.stopPropagation();
  document.getElementById("ext-menu").classList.toggle("hidden");
}

document.addEventListener("click", (e) => {
  if (!e.target.closest("#ext-filter-container")) {
    document.getElementById("ext-menu").classList.add("hidden");
  }
});

function applyExtFilters() {
  extensionFilters.clear();
  const checks = document.querySelectorAll(
    '#ext-menu input[type="checkbox"]:checked',
  );
  checks.forEach((c) => extensionFilters.add(c.value));

  const btn = document.getElementById("ext-btn");
  if (extensionFilters.size === 0) btn.textContent = "Formatos: Todos ▼";
  else btn.textContent = `Formatos: ${extensionFilters.size} selec. ▼`;

  renderContent();
}

function updateExtensionDropdown(files) {
  const menu = document.getElementById("ext-menu");
  menu.innerHTML = "";

  const exts = new Set();
  files.forEach((f) => {
    if (f.name.includes(".")) {
      exts.add(f.name.split(".").pop().toLowerCase());
    }
  });

  if (exts.size === 0) {
    menu.innerHTML =
      '<div style="padding:4px;color:#999;font-size:11px;">Sin extensiones</div>';
    return;
  }

  Array.from(exts)
    .sort()
    .forEach((ext) => {
      const lbl = document.createElement("label");
      lbl.innerHTML = `<input type="checkbox" value="${ext}" onchange="applyExtFilters()"> .${ext}`;
      menu.appendChild(lbl);
    });
}

function setView(mode) {
  viewMode = mode;
  document
    .getElementById("btn-grid")
    .classList.toggle("active", mode === "grid");
  document
    .getElementById("btn-list")
    .classList.toggle("active", mode === "list");
  renderContent();
}

function handleFilesLoaded(filesArray) {
  if (!filesArray.length) return;

  allFiles = filesArray;

  // Generar un ID único para cada archivo de forma que sea infalible en la selección
  allFiles.forEach((f, index) => {
    f._id = f.webkitRelativePath || f.name + "-" + index;
  });

  updateExtensionDropdown(allFiles);
  extensionFilters.clear();
  document.getElementById("ext-btn").textContent = "Formatos: Todos ▼";

  const tree = buildTree(allFiles);
  folderTree = tree;
  const treeEl = document.getElementById("tree");
  treeEl.innerHTML = "";
  renderTree(tree, treeEl, 0, "");
  const first = Object.keys(tree)[0];
  if (first) {
    treeEl.querySelector(".tree-item")?.classList.add("active");
    navigateTo(tree[first], first);
  }
}

document.getElementById("dir-input").addEventListener("change", function () {
  handleFilesLoaded(Array.from(this.files));
});
document.getElementById("file-input").addEventListener("change", function () {
  handleFilesLoaded(Array.from(this.files));
});
