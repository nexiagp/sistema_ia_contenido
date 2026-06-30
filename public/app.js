const app = {
  state: null,
  view: location.hash?.replace("#", "") || "generator",
  busy: false,
  settingsTab: "general",       // general | posts | blog | prompts
  editingPromptId: null,
  editingPromptDetail: null,
  promptHistoryOpen: false,
};

const PROMPT_GROUP_LABELS = {
  core_posts: "Posts · Core",
  post_types: "Posts · Tipos",
  transformers: "Posts · Adaptadores",
  blog: "Blog",
};

const titles = {
  generator: "Sistema editorial IA",
  posts: "Revisión editorial",
  blogs: "Blogs web",
  library: "Biblioteca y fuentes",
  strategy: "Prompts versionados",
  automation: "Automatización",
  settings: "Ajustes",
};

const statusLabels = {
  draft: "Borrador",
  ready: "Listo",
  published: "Publicado",
  scheduled: "Programado",
};

document.addEventListener("DOMContentLoaded", async () => {
  injectStaticIcons();
  bindEvents();
  await loadState();
});

function bindEvents() {
  document.addEventListener("input", (event) => {
    if (!event.target) return;
    if (event.target.id === "postsSearch") {
      app.postFilters = app.postFilters || { status: "all", q: "" };
      app.postFilters.q = event.target.value;
      renderPostsList();
    }
    if (event.target.id === "blogsSearch") {
      app.blogFilters = app.blogFilters || { status: "all", q: "" };
      app.blogFilters.q = event.target.value;
      renderBlogList();
    }
  });

  document.addEventListener("click", async (event) => {
    const nav = event.target.closest("[data-nav]");
    if (nav) {
      setView(nav.dataset.nav);
      return;
    }

    const action = event.target.closest("[data-action]");
    if (!action) return;

    try {
      const name = action.dataset.action;

      if (name === "refresh") await loadState("Actualizado");
      if (name === "generate-open") setView("generator");

      if (name === "copy-final") {
        const post = findPost(action.dataset.id);
        await navigator.clipboard.writeText(formatFinalPost(post));
        toast("Post copiado");
      }

      if (name === "copy-adaptation") {
        const post = findPost(action.dataset.id);
        await navigator.clipboard.writeText(getAdaptationText(post, action.dataset.channel));
        toast("Adaptación copiada");
      }

      if (name === "post-status") {
        await withLoading(action, () =>
          api(`/api/posts/${action.dataset.id}`, {
            method: "PATCH",
            body: JSON.stringify({ status: action.dataset.status }),
          }),
        );
        await loadState("Estado actualizado");
      }

      if (name === "post-publish") {
        await withLoading(action, () => api(`/api/posts/${action.dataset.id}/publish`, { method: "POST" }));
        await loadState("Post enviado");
      }

      if (name === "post-delete") {
        if (!confirm("Eliminar este post del registro?")) return;
        await withLoading(action, () => api(`/api/posts/${action.dataset.id}`, { method: "DELETE" }));
        await loadState("Post eliminado");
      }

      if (name === "post-edit") {
        app.editingPostId = action.dataset.id;
        renderPostsList();
        return;
      }

      if (name === "post-edit-cancel") {
        app.editingPostId = null;
        renderPostsList();
        return;
      }

      if (name === "post-edit-save") {
        const card = action.closest(".editorial-review");
        const payload = {
          copy: card?.querySelector(".edit-copy")?.value ?? "",
          hashtags: card?.querySelector(".edit-hashtags")?.value ?? "",
          cta: card?.querySelector(".edit-cta")?.value ?? "",
        };
        await withLoading(action, () =>
          api(`/api/posts/${action.dataset.id}`, { method: "PATCH", body: JSON.stringify(payload) }),
        );
        app.editingPostId = null;
        await loadState("Post actualizado");
        return;
      }

      if (name === "posts-filter") {
        app.postFilters = app.postFilters || { status: "all", q: "" };
        app.postFilters.status = action.dataset.status || "all";
        renderPosts();
        return;
      }

      if (name === "posts-export-csv") {
        const posts = getFilteredPosts();
        if (!posts.length) return toast("No hay posts que exportar", true);
        downloadFile("nexiagp-posts.csv", "﻿" + postsToCsv(posts), "text/csv");
        toast(`${posts.length} posts exportados a CSV`);
        return;
      }

      if (name === "posts-export-json") {
        const posts = getFilteredPosts();
        if (!posts.length) return toast("No hay posts que exportar", true);
        downloadFile("nexiagp-posts.json", JSON.stringify(posts, null, 2), "application/json");
        toast(`${posts.length} posts exportados a JSON`);
        return;
      }

      if (name === "channel-preview-toggle") {
        const panel = document.getElementById(`channel-preview-${action.dataset.id}`);
        if (panel) {
          const open = panel.style.display !== "none";
          panel.style.display = open ? "none" : "block";
          action.classList.toggle("is-active", !open);
        }
        return;
      }

      if (name === "image-panel-toggle") {
        const panel = document.getElementById(`img-opts-${action.dataset.id}`);
        if (panel) {
          const open = panel.style.display !== "none";
          panel.style.display = open ? "none" : "grid";
          action.classList.toggle("is-active", !open);
        }
        return;
      }

      if (name === "generate-image") {
        const postId = action.dataset.id;
        const panel = document.getElementById(`img-opts-${postId}`);
        const size = panel?.querySelector(".img-size")?.value || "1344x768";
        const quality = panel?.querySelector(".img-quality")?.value || "medium";
        const style = panel?.querySelector(".img-style")?.value || "Fotografía documental editorial";
        const userNotes = panel?.querySelector(".img-notes")?.value || "";
        const withFrame = panel?.querySelector(".img-frame")?.checked ?? true;
        await withLoading(action, () =>
          api(`/api/posts/${postId}/generate-image`, {
            method: "POST",
            body: JSON.stringify({ size, quality, style, userNotes, withFrame }),
          }),
        );
        await loadState("Imagen generada");
        return;
      }

      if (name === "regenerate") {
        const instruction = action.dataset.instruction || "Regenera la pieza completa manteniendo la estrategia.";
        await withLoading(action, () =>
          api(`/api/editorial/posts/${action.dataset.id}/regenerate`, {
            method: "POST",
            body: JSON.stringify({ instruction }),
          }),
        );
        await loadState("Nueva versión generada");
        setView("posts");
      }

      if (name === "adapt") {
        await withLoading(action, () => api(`/api/editorial/posts/${action.dataset.id}/adapt`, { method: "POST" }));
        await loadState("Adaptaciones generadas");
      }

      if (name === "file-delete") {
        if (!confirm("Eliminar este archivo de la biblioteca?")) return;
        await withLoading(action, () => api(`/api/files/${action.dataset.id}`, { method: "DELETE" }));
        await loadState("Archivo eliminado");
      }

      if (name === "import-local") {
        await withLoading(action, () => api("/api/files/import-local", { method: "POST" }));
        await loadState("Documentación importada");
      }

      if (name === "sync-openai") {
        await withLoading(action, () => api("/api/files/sync-openai", { method: "POST" }));
        await loadState("Biblioteca sincronizada");
      }

      if (name === "blogs-filter") {
        app.blogFilters = app.blogFilters || { status: "all", q: "" };
        app.blogFilters.status = action.dataset.status || "all";
        const bar = document.getElementById("blogsToolbar");
        bar?.querySelectorAll("[data-action='blogs-filter']").forEach((b) =>
          b.classList.toggle("is-active", b.dataset.status === app.blogFilters.status),
        );
        renderBlogList();
        return;
      }

      if (name === "blog-select") {
        app.selectedBlogId = action.dataset.id;
        renderBlogs();
        return;
      }

      if (name === "blog-tab") {
        const tab = action.dataset.tab;
        document.querySelectorAll(".blog-tabs .tab").forEach((t) => t.classList.toggle("is-active", t.dataset.tab === tab));
        document.querySelectorAll("[data-tab-content]").forEach((c) => c.classList.toggle("hidden", c.dataset.tabContent !== tab));
        return;
      }

      if (name === "blog-copy-html") {
        const blog = (app.state.blogs || []).find((b) => b.id === action.dataset.id);
        if (blog) {
          const html = blog.article?.article_html_override || blog.article?.article_html || "";
          await navigator.clipboard.writeText(injectFigureImages(html, blog.figures || []));
          toast("HTML copiado al portapapeles");
        }
        return;
      }

      if (name === "blog-download") {
        const blog = (app.state.blogs || []).find((b) => b.id === action.dataset.id);
        if (blog) {
          const html = injectFigureImages(blog.article?.article_html_override || blog.article?.article_html || "", blog.figures || []);
          const full = await buildStandaloneDocument(html, blog);
          const blob = new Blob([full], { type: "text/html;charset=utf-8" });
          const a = document.createElement("a");
          a.href = URL.createObjectURL(blob);
          a.download = `${blog.slug || blog.id}.html`;
          a.click();
          URL.revokeObjectURL(a.href);
        }
        return;
      }

      if (name === "blog-status") {
        await withLoading(action, () =>
          api(`/api/blogs/${action.dataset.id}`, {
            method: "PATCH",
            body: JSON.stringify({ status: action.dataset.status }),
          }),
        );
        await loadState("Estado actualizado");
        return;
      }

      if (name === "blog-delete") {
        if (!confirm("Eliminar este blog del registro?")) return;
        await withLoading(action, () => api(`/api/blogs/${action.dataset.id}`, { method: "DELETE" }));
        app.selectedBlogId = null;
        await loadState("Blog eliminado");
        return;
      }

      if (name === "blog-figure-generate") {
        const blogId = action.dataset.blog;
        const figId = action.dataset.fig;
        const panel = document.getElementById(`figopts-${blogId}-${figId}`);
        const size = panel?.querySelector(".fig-size")?.value || "1344x768";
        const quality = panel?.querySelector(".fig-quality")?.value || "medium";
        const withFrame = panel?.querySelector(".fig-frame")?.checked ?? true;
        const userNotes = panel?.querySelector(".fig-notes")?.value || "";
        await withLoading(action, () =>
          api(`/api/blogs/${blogId}/figures/${figId}/generate-image`, {
            method: "POST",
            body: JSON.stringify({ size, quality, withFrame, userNotes }),
          }),
        );
        await loadState("Imagen generada");
        return;
      }

      if (name === "scheduler-run") {
        await withLoading(action, () => api("/api/scheduler/run", { method: "POST" }));
        await loadState("Automatización ejecutada");
      }

      // --- Settings: internal tabs + prompt editor ---

      if (name === "settings-tab") {
        app.settingsTab = action.dataset.tab || "general";
        app.editingPromptId = null;
        app.editingPromptDetail = null;
        app.promptHistoryOpen = false;
        renderSettings();
        if (app.view !== "settings") setView("settings");
        return;
      }

      if (name === "prompt-open") {
        const id = action.dataset.id;
        app.editingPromptId = id;
        app.promptHistoryOpen = false;
        renderSettings();
        try {
          const res = await fetchJson(`/api/prompts/${encodeURIComponent(id)}`);
          app.editingPromptDetail = res.prompt;
          renderSettings();
        } catch (error) {
          app.editingPromptId = null;
          renderSettings();
          toast(error.message, true);
        }
        return;
      }

      if (name === "prompt-close") {
        app.editingPromptId = null;
        app.editingPromptDetail = null;
        app.promptHistoryOpen = false;
        renderSettings();
        return;
      }

      if (name === "prompt-history-toggle") {
        app.promptHistoryOpen = !app.promptHistoryOpen;
        renderSettings();
        return;
      }

      if (name === "prompt-revert") {
        const id = action.dataset.id;
        const version = Number(action.dataset.version || 0);
        if (!version || !confirm(`Restaurar la versión ${version} como prompt activo?`)) return;
        const res = await withLoading(action, () =>
          api(`/api/prompts/${encodeURIComponent(id)}/revert`, {
            method: "POST",
            body: JSON.stringify({ version }),
          }),
        );
        app.editingPromptDetail = res.prompt;
        if (res.state) {
          app.state = res.state;
          render();
        } else {
          await loadState();
        }
        toast(`Restaurada v${version}`);
        return;
      }
    } catch (error) {
      toast(error.message, true);
    }
  });

  document.addEventListener("submit", async (event) => {
    const form = event.target;
    event.preventDefault();
    try {
      if (form.id === "editorialForm") {
        const payload = Object.fromEntries(new FormData(form));
        payload.usar_enlace = form.usar_enlace.checked;
        payload.necesita_adaptacion_multicanal = form.necesita_adaptacion_multicanal.checked;
        await withLoading(form.querySelector("button[type='submit']"), () =>
          api("/api/editorial/generate", {
            method: "POST",
            body: JSON.stringify(payload),
          }),
        );
        await loadState("Pipeline editorial completado");
        setView("posts");
      }

      if (form.id === "blogForm") {
        const payload = Object.fromEntries(new FormData(form));
        await withLoading(form.querySelector("button[type='submit']"), () =>
          api("/api/blogs/generate", {
            method: "POST",
            body: JSON.stringify(payload),
          }),
        );
        app.selectedBlogId = null;
        await loadState("Blog generado");
        return;
      }

      if (form.id === "uploadForm") {
        const data = new FormData(form);
        await withLoading(form.querySelector("button[type='submit']"), () =>
          fetchJson("/api/files/upload", { method: "POST", body: data }),
        );
        form.reset();
        await loadState("Archivo subido");
      }

      if (form.id === "automationForm" || form.id === "settingsForm") {
        const data = Object.fromEntries(new FormData(form));
        await withLoading(form.querySelector("button[type='submit']"), () =>
          api("/api/settings", {
            method: "PATCH",
            body: JSON.stringify({
              model: data.model,
              vectorStoreId: data.vectorStoreId,
              vectorStoreName: data.vectorStoreName,
              cadenceDays: Number(data.cadenceDays || 3),
              defaultPostTypeId: data.defaultPostTypeId,
              publishMode: data.publishMode,
              schedulerEnabled: data.schedulerEnabled === "on",
            }),
          }),
        );
        await loadState("Ajustes guardados");
      }

      if (form.id === "settingsFormBlog") {
        const data = Object.fromEntries(new FormData(form));
        await withLoading(form.querySelector("button[type='submit']"), () =>
          api("/api/settings", {
            method: "PATCH",
            body: JSON.stringify({
              blog: {
                defaultModel: data.defaultModel,
                defaultLength: data.defaultLength,
                defaultFramework: data.defaultFramework,
                defaultAudience: data.defaultAudience,
                imagesPerArticle: Number(data.imagesPerArticle || 2),
                imageQuality: data.imageQuality,
                costTargetCents: Number(data.costTargetCents || 30),
              },
            }),
          }),
        );
        await loadState("Ajustes de blog guardados");
        app.settingsTab = "blog";
        renderSettings();
      }

      if (form.id === "promptEditorForm") {
        const id = form.dataset.id;
        const text = form.querySelector("textarea[name='text']")?.value || "";
        const note = form.querySelector("input[name='note']")?.value || "";
        const res = await withLoading(form.querySelector("button[type='submit']"), () =>
          api(`/api/prompts/${encodeURIComponent(id)}`, {
            method: "PUT",
            body: JSON.stringify({ text, note }),
          }),
        );
        app.editingPromptDetail = res.prompt;
        if (res.state) {
          app.state = res.state;
          render();
        } else {
          await loadState();
        }
        toast("Prompt guardado");
      }
    } catch (error) {
      toast(error.message, true);
    }
  });
}

async function loadState(message) {
  app.state = await fetchJson("/api/state");
  render();
  if (message) toast(message);
}

function render() {
  renderMetrics();
  renderConnection();
  renderNotices();
  renderGenerator();
  renderPosts();
  renderBlogs();
  renderLibrary();
  renderStrategy();
  renderAutomation();
  renderSettings();
  updateView();
}

function setView(view) {
  app.view = view;
  updateView();
  history.replaceState(null, "", `#${view}`);
}

function updateView() {
  document.querySelectorAll(".view").forEach((section) => section.classList.toggle("is-active", section.dataset.view === app.view));
  document.querySelectorAll(".nav-item").forEach((button) => button.classList.toggle("is-active", button.dataset.nav === app.view));
  document.getElementById("viewTitle").textContent = titles[app.view] || "Nexia GP Social AI";
}

function renderMetrics() {
  const { counts } = app.state;
  const usage = app.state.usageStats || {};
  document.getElementById("metrics").innerHTML = [
    metric("Posts", counts.posts),
    metric("Borradores", counts.draft),
    metric("Listos", counts.ready),
    metric("Publicados", counts.published),
    metric("Archivos", counts.files),
    metric("Tokens", formatTokens(usage.total_tokens || 0)),
  ].join("");
}

function formatTokens(n) {
  n = Number(n) || 0;
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

function renderConnection() {
  document.getElementById("connectionStatus").innerHTML = `
    <div class="status-row">
      ${badge(app.state.hasOpenAIKey ? "OpenAI activo" : "Pipeline local", app.state.hasOpenAIKey ? "published" : "draft")}
      ${badge(app.state.settings.vectorStoreId ? "Vector Store" : "Sin Vector Store", app.state.settings.vectorStoreId ? "published" : "draft")}
    </div>
  `;
}

function renderNotices() {
  const notices = [];
  if (!app.state.hasOpenAIKey) {
    notices.push("OPENAI_API_KEY no está configurada. El pipeline funciona en modo local con retrieval documental básico.");
  }
  if (app.state.hasOpenAIKey && !app.state.settings.vectorStoreId) {
    notices.push("Importa o sube documentos para crear la Vector Store y activar file search.");
  }
  document.getElementById("noticeHost").innerHTML = notices
    .map((text) => `<div class="notice">${iconSvg("alert")}<span>${escapeHtml(text)}</span></div>`)
    .join("");
}

function renderGenerator() {
  const options = app.state.editorialOptions;
  const latest = app.state.posts.find((post) => post.source === "editorial_pipeline");
  document.getElementById("generatorView").innerHTML = `
    <div class="editorial-layout">
      <form class="panel form-grid" id="editorialForm">
        <div class="two-cols">
          ${selectField("canal", "Canal", options.channels, "linkedin")}
          ${selectField("tipo_post", "Tipo de post", options.postTypes, "auto")}
        </div>
        <div class="two-cols">
          ${selectField("audiencia_principal", "Audiencia", options.audiences, "fabricantes")}
          ${selectField("objetivo", "Objetivo", options.objectives, "autoridad")}
        </div>
        <div class="two-cols">
          <label>Sector<input name="sector" placeholder="Ej. suministro industrial, garden, hotelero" /></label>
          <label>Marca / tema<input name="marca_o_entidad" placeholder="Opcional, solo si hay fuente aprobada" /></label>
        </div>
        <label>Tema libre<textarea name="tema_libre" placeholder="Ej. por qué la reposición cambia la implantación comercial en Canarias"></textarea></label>
        <div class="two-cols">
          ${selectField("cta_preferida", "CTA", options.ctaTypes, "comentario")}
          ${selectField("nivel_promocional", "Promoción", options.promotionalLevels, "bajo")}
        </div>
        <label>Notas humanas<textarea name="notas_humanas" placeholder="Restricciones, enfoque, matices de cliente o fuente concreta"></textarea></label>
        <div class="switch-row">
          <span>Usar enlace si procede</span>
          <input name="usar_enlace" type="checkbox" />
        </div>
        <div class="switch-row">
          <span>Generar adaptación a X y Facebook</span>
          <input name="necesita_adaptacion_multicanal" type="checkbox" checked />
        </div>
        <div class="actions">
          <button class="primary-button" type="submit">${iconSvg("spark")}Ejecutar pipeline</button>
          <button class="ghost-button" type="button" data-nav="library">${iconSvg("folder")}Fuentes</button>
        </div>
      </form>

      <div class="panel">
        <h3>Flujo editorial</h3>
        <div class="pipeline-steps">
          ${step("Planner", "Brief estratégico")}
          ${step("Retrieval", "Fuentes y contexto")}
          ${step("Writer", "Post + hooks")}
          ${step("Validator", "Riesgo y versión final")}
          ${step("Adapters", "X y Facebook")}
        </div>
        ${latest ? latestSummary(latest) : `<div class="empty">Aún no hay generaciones editoriales.</div>`}
      </div>
    </div>
  `;
}

function allEditorialPosts() {
  return app.state.posts.filter((post) => post.source === "editorial_pipeline" || post.generation);
}

function getFilteredPosts() {
  const f = app.postFilters || (app.postFilters = { status: "all", q: "" });
  const q = (f.q || "").trim().toLowerCase();
  return allEditorialPosts().filter((post) => {
    if (f.status !== "all" && (post.status || "draft") !== f.status) return false;
    if (q) {
      const hay = [post.title, post.idea, post.copy, (post.generation?.copy?.final_post)]
        .filter(Boolean).join(" ").toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
}

function postsToolbar() {
  const f = app.postFilters || { status: "all", q: "" };
  const chip = (id, label) =>
    `<button type="button" class="filter-chip ${f.status === id ? "is-active" : ""}" data-action="posts-filter" data-status="${id}">${label}</button>`;
  return `
    <div class="list-toolbar" id="postsToolbar">
      <div class="filter-chips">
        ${chip("all", "Todos")}
        ${chip("draft", "Borradores")}
        ${chip("ready", "Listos")}
        ${chip("published", "Publicados")}
      </div>
      <div class="toolbar-right">
        <input id="postsSearch" class="list-search" type="search" placeholder="Buscar en posts…" value="${escapeAttr(f.q || "")}" />
        <button type="button" class="ghost-button" data-action="posts-export-csv" title="Exportar lo filtrado a CSV">${iconSvg("upload")}CSV</button>
        <button type="button" class="ghost-button" data-action="posts-export-json" title="Exportar lo filtrado a JSON">${iconSvg("upload")}JSON</button>
      </div>
    </div>`;
}

function downloadFile(name, content, mime) {
  const blob = new Blob([content], { type: `${mime};charset=utf-8` });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}

function postsToCsv(posts) {
  const cols = ["id", "status", "postType", "createdAt", "title", "copy", "cta", "hashtags"];
  const esc = (v) => `"${String(v == null ? "" : v).replace(/"/g, '""')}"`;
  const rows = posts.map((p) =>
    [
      p.id,
      p.status,
      p.postTypeId || p.brief?.post_type || "",
      p.createdAt || "",
      p.title || "",
      p.generation?.copy?.final_post || p.copy || "",
      p.cta || "",
      (p.hashtags || p.generation?.copy?.hashtags || []).join(" "),
    ]
      .map(esc)
      .join(","),
  );
  return [cols.join(","), ...rows].join("\r\n");
}

function renderPosts() {
  const host = document.getElementById("postsView");
  if (!host.querySelector("#postsToolbar")) {
    host.innerHTML = `${postsToolbar()}<div class="editorial-feed" id="postsList"></div>`;
  } else {
    // refresca solo el estado activo de los chips, sin tocar el input de busqueda
    host.querySelectorAll("[data-action='posts-filter']").forEach((b) =>
      b.classList.toggle("is-active", b.dataset.status === (app.postFilters?.status || "all")),
    );
  }
  renderPostsList();
}

function renderPostsList() {
  const list = document.getElementById("postsList");
  if (!list) return;
  const posts = getFilteredPosts();
  const total = allEditorialPosts().length;
  list.innerHTML = posts.length
    ? posts.map(editorialPostCard).join("")
    : `<div class="empty">${total ? "Ningún post coincide con el filtro." : "Sin posts editoriales todavía."}</div>`;
}

function channelPreview(post) {
  const copy = (post.generation && post.generation.copy) || {};
  const li = copy.final_post || post.copy || "";
  const tags = copy.hashtags || post.hashtags || [];
  const ad = post.adaptations || {};
  const xText = (ad.x || {}).short_version || "";
  const fb = (ad.facebook || {}).final_post || "";
  const nl = (s) => escapeHtml(s).replace(/\n/g, "<br>");
  const xOver = xText.length > 280;
  return `
    <div class="channel-preview" id="channel-preview-${escapeAttr(post.id)}" style="display:none">
      <div class="cp-grid">
        <div class="cp-card cp-linkedin">
          <div class="cp-head"><span class="cp-avatar">NGP</span><div class="cp-id"><strong>Nexia Growth Partner</strong><small>Agencia comercial B2B · Canarias</small></div><span class="cp-logo">in</span></div>
          <div class="cp-body">${li ? nl(li) : "<em>Sin texto</em>"}</div>
          ${tags.length ? `<div class="cp-tags">${tags.map((t) => `<span>${escapeHtml(t)}</span>`).join(" ")}</div>` : ""}
          <div class="cp-meta">${li.length} caracteres</div>
        </div>
        <div class="cp-card cp-x">
          <div class="cp-head"><span class="cp-avatar">NGP</span><div class="cp-id"><strong>Nexia GP</strong><small>@nexiagp</small></div><span class="cp-logo">X</span></div>
          <div class="cp-body">${xText ? nl(xText) : "<em>Sin adaptación a X</em>"}</div>
          ${xText ? `<div class="cp-meta ${xOver ? "cp-over" : "cp-ok"}">${xText.length}/280${xOver ? " · excede" : ""}</div>` : ""}
        </div>
        <div class="cp-card cp-fb">
          <div class="cp-head"><span class="cp-avatar">NGP</span><div class="cp-id"><strong>Nexia Growth Partner</strong><small>Facebook</small></div><span class="cp-logo">f</span></div>
          <div class="cp-body">${fb ? nl(fb) : "<em>Sin adaptación a Facebook</em>"}</div>
          ${fb ? `<div class="cp-meta">${fb.length} caracteres</div>` : ""}
        </div>
      </div>
    </div>`;
}

function editorialPostCard(post) {
  const brief = post.brief || {};
  const generation = post.generation || {};
  const copy = generation.copy || {};
  const support = generation.editorial_support || {};
  const retrieval = post.retrieval || {};
  const validation = post.validation || {};
  const adaptations = post.adaptations || {};
  const wordCount = (copy.final_post || post.copy || "").trim().split(/\s+/).filter(Boolean).length;
  const sourceCount = (retrieval.sources || []).length;
  return `
    <article class="editorial-review">
      <header class="review-hero">
        <div class="review-title-block">
          <div class="status-row">
            ${badge(statusLabels[post.status] || post.status || "Borrador", post.status || "draft")}
            ${badge(labelFor("postTypes", brief.post_type), "published")}
            ${badge(labelFor("audiences", brief.audience), "")}
            ${badge(post.provider || "pipeline", "")}
          </div>
          <h3>${escapeHtml(brief.core_angle || post.title || "Post editorial")}</h3>
          <p>${escapeHtml(brief.core_thesis || post.idea || "")}</p>
        </div>
        <div class="review-scoreboard">
          ${reviewStat("Fuentes", sourceCount)}
          ${reviewStat("Palabras", wordCount)}
          ${reviewStat("Riesgo", validation.risk_level || "low")}
          ${reviewStat("Flags", (validation.review_flags || []).length)}
        </div>
      </header>

      <div class="review-main">
        <section class="review-primary">
          <div class="section-label">
            <span>${iconSvg("check")}</span>
            <div>
              <p class="eyebrow">Versión validada</p>
              <h3>Post final</h3>
            </div>
          </div>
          ${app.editingPostId === post.id ? `
          <div class="final-post-sheet editing">
            <label class="edit-label">Post final<textarea class="edit-copy" rows="10">${escapeHtml(copy.final_post || post.copy || "")}</textarea></label>
            <label class="edit-label">Hashtags (separados por espacio)<input class="edit-hashtags" value="${escapeAttr((copy.hashtags || post.hashtags || []).join(" "))}" /></label>
            <label class="edit-label">CTA<input class="edit-cta" value="${escapeAttr(copy.cta || post.cta || "")}" /></label>
          </div>
          <div class="actions">
            <button class="primary-button" type="button" data-action="post-edit-save" data-id="${escapeAttr(post.id)}">${iconSvg("check")}Guardar cambios</button>
            <button class="ghost-button" type="button" data-action="post-edit-cancel" data-id="${escapeAttr(post.id)}">Cancelar</button>
          </div>` : `
          <div class="final-post-sheet">
            <p>${escapeHtml(copy.final_post || post.copy || "")}${post.edited ? ` <span class="edited-tag">editado</span>` : ""}</p>
            <div class="card-meta">${(copy.hashtags || post.hashtags || []).map((tag) => `<span class="pill">${escapeHtml(tag)}</span>`).join("")}</div>
            ${copy.cta || post.cta ? `<div class="cta-strip"><span>CTA</span><strong>${escapeHtml(copy.cta || post.cta)}</strong></div>` : ""}
          </div>
          <div class="actions">
            <button class="primary-button" type="button" data-action="copy-final" data-id="${escapeAttr(post.id)}">${iconSvg("copy")}Copiar post</button>
            <button class="secondary-button" type="button" data-action="post-edit" data-id="${escapeAttr(post.id)}">${iconSvg("layout")}Editar</button>
            <button class="secondary-button" type="button" data-action="channel-preview-toggle" data-id="${escapeAttr(post.id)}">${iconSvg("layout")}Previsualizar</button>
            <button class="secondary-button" type="button" data-action="adapt" data-id="${escapeAttr(post.id)}">${iconSvg("refresh")}Regenerar adaptaciones</button>
          </div>
          ${channelPreview(post)}`}
        </section>

        <aside class="review-sidebar">
          <section class="review-panel">
            <div class="section-label compact">
              <span>${iconSvg("target")}</span>
              <h3>Brief</h3>
            </div>
            ${kv("Por qué importa", brief.why_it_matters)}
            ${kv("CTA", brief.cta_type)}
            ${kv("Sensibilidad", brief.factual_sensitivity)}
          </section>
          <section class="review-panel">
            <div class="section-label compact">
              <span>${iconSvg("alert")}</span>
              <h3>Revisión</h3>
            </div>
            ${flagList(validation.review_flags || [])}
            ${kv("Humana", validation.human_review_required ? "Sí" : "Normal")}
            ${(validation.validation_notes || []).map((note) => `<p class="note-line">${escapeHtml(note)}</p>`).join("")}
          </section>
        </aside>
      </div>

      <div class="review-support-grid">
        <section class="review-panel">
          <div class="section-label compact">
            <span>${iconSvg("spark")}</span>
            <h3>Hooks alternativos</h3>
          </div>
          ${hookOption("A", copy.hook_option_1)}
          ${hookOption("B", copy.hook_option_2)}
        </section>

        <section class="review-panel">
          <div class="section-label compact">
            <span>${iconSvg("clock")}</span>
            <h3>Reactivación</h3>
          </div>
          <p class="copy-block emphasis">${escapeHtml(support.reactivation_comment_8_24h || "")}</p>
          <div class="section-label compact small-gap">
            <span>${iconSvg("layout")}</span>
            <h3>Idea visual</h3>
          </div>
          <p class="copy-block">${escapeHtml(support.visual_brief || "")}</p>
        </section>
      </div>

      <section class="review-panel">
        <div class="section-label compact">
          <span>${iconSvg("folder")}</span>
          <h3>Fuentes usadas</h3>
        </div>
        ${sourceList(retrieval.sources || [])}
      </section>

      <section class="review-panel">
        <div class="section-label compact">
          <span>${iconSvg("send")}</span>
          <h3>Adaptaciones multicanal</h3>
        </div>
        ${adaptationBlocks(post.id, adaptations)}
      </section>

      ${imageSection(post)}

      <footer class="review-actions">
        <button class="ghost-button" type="button" data-action="regenerate" data-id="${escapeAttr(post.id)}" data-instruction="Hazlo menos promocional y mas basado en criterio de mercado.">${iconSvg("undo")}Menos promocional</button>
        <button class="ghost-button" type="button" data-action="regenerate" data-id="${escapeAttr(post.id)}" data-instruction="Hazlo mas util, con una lectura practica mas clara.">${iconSvg("target")}Más útil</button>
        <button class="ghost-button" type="button" data-action="regenerate" data-id="${escapeAttr(post.id)}" data-instruction="Hazlo mas corto sin perder la idea central.">${iconSvg("layout")}Más corto</button>
        <button class="secondary-button" type="button" data-action="post-status" data-status="ready" data-id="${escapeAttr(post.id)}">${iconSvg("check")}Listo</button>
        <button class="primary-button" type="button" data-action="post-publish" data-id="${escapeAttr(post.id)}">${iconSvg("send")}Publicar</button>
        <button class="danger-button" type="button" data-action="post-delete" data-id="${escapeAttr(post.id)}">${iconSvg("trash")}Eliminar</button>
      </footer>
    </article>
  `;
}

function blogsToolbar() {
  const f = app.blogFilters || { status: "all", q: "" };
  const chip = (id, label) =>
    `<button type="button" class="filter-chip ${f.status === id ? "is-active" : ""}" data-action="blogs-filter" data-status="${id}">${label}</button>`;
  return `
    <div class="list-toolbar compact" id="blogsToolbar">
      <div class="filter-chips">
        ${chip("all", "Todos")}
        ${chip("draft", "Borradores")}
        ${chip("ready", "Listos")}
        ${chip("published", "Publicados")}
      </div>
      <input id="blogsSearch" class="list-search" type="search" placeholder="Buscar blogs…" value="${escapeAttr(f.q || "")}" />
    </div>`;
}

function getFilteredBlogs() {
  const blogs = app.state.blogs || [];
  const f = app.blogFilters || (app.blogFilters = { status: "all", q: "" });
  const q = (f.q || "").trim().toLowerCase();
  return blogs.filter((b) => {
    if (f.status !== "all" && (b.status || "draft") !== f.status) return false;
    if (q) {
      const hay = [b.title, b.metaTitle, b.metaDescription, b.slug].filter(Boolean).join(" ").toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
}

function renderBlogList() {
  const host = document.getElementById("blogList");
  if (!host) return;
  const blogs = getFilteredBlogs();
  const selectedId = app.selectedBlogId || (blogs[0] && blogs[0].id);
  const total = (app.state.blogs || []).length;
  host.innerHTML = blogs.length
    ? blogs.map((b) => blogListItem(b, selectedId)).join("")
    : `<div class="empty">${total ? "Ningún blog coincide con el filtro." : "Aún no hay blogs generados."}</div>`;
}

function renderBlogs() {
  const blogOpts = app.state.blogOptions || {};
  const blogs = app.state.blogs || [];
  const blogCfg = (app.state.settings && app.state.settings.blog) || {};
  const selectedId = app.selectedBlogId || (blogs[0] && blogs[0].id);
  const selected = blogs.find((b) => b.id === selectedId) || blogs[0];

  const counts = app.state.counts || {};
  const cfgImageQualityLabel = { low: "ligera", standard: "estándar", high: "alta" }[blogCfg.imageQuality || "standard"] || "estándar";

  document.getElementById("blogsView").innerHTML = `
    <div class="blogs-template-bar">
      <div class="blogs-template-info">
        <strong>Plantilla activa:</strong>
        <span class="pill">longitud ${escapeHtml(blogCfg.defaultLength || "medio")}</span>
        <span class="pill">framework ${escapeHtml((blogCfg.defaultFramework || "pas").toUpperCase())}</span>
        <span class="pill">${blogCfg.imagesPerArticle ?? 2} imágenes (${escapeHtml(cfgImageQualityLabel)}, sin marco)</span>
        <span class="pill">CTA fija "¿Comenzamos? · Contactar"</span>
      </div>
      <div class="blogs-template-actions">
        <span class="muted">${counts.blogs || 0} totales · ${counts.blogsDraft || 0} borradores · ${counts.blogsReady || 0} listos · ${counts.blogsPublished || 0} publicados</span>
        <button class="ghost-button" type="button" data-action="settings-tab" data-tab="blog">${iconSvg("settings")}Ajustes de Blog</button>
      </div>
    </div>

    <div class="blogs-layout">
      <aside class="blogs-sidebar">
        <form class="panel form-grid" id="blogForm">
          <h3>Generar nuevo blog</h3>
          <label>Tema / tesis libre
            <textarea name="topic" rows="3" placeholder="Ej: por qué la prescripción técnica decide la implantación de un fabricante en hotelero canario" required></textarea>
          </label>
          <div class="two-cols">
            ${blogSelect("search_intent_hint", "Intención de búsqueda", blogOpts.searchIntents, "informational")}
            ${blogSelect("framework_hint", "Framework", blogOpts.frameworks, blogCfg.defaultFramework || "pas")}
          </div>
          <div class="two-cols">
            ${blogSelect("audience", "Audiencia", blogOpts.audiences, blogCfg.defaultAudience || "mixta")}
            ${blogSelect("length", "Longitud", blogOpts.lengths, blogCfg.defaultLength || "medio")}
          </div>
          <label>Sector<input name="sector" placeholder="Ej. hotelero, suministro industrial, garden" /></label>
          <div class="two-cols">
            ${blogSelect("cta_type", "CTA temático del cuerpo", blogOpts.ctaTypes, "consulta_servicios")}
            <label>Marca / entidad<input name="marca_o_entidad" placeholder="Opcional" /></label>
          </div>
          <div class="two-cols">
            <label>Imágenes
              <input name="images_per_article" type="number" min="0" max="6" value="${escapeAttr(blogCfg.imagesPerArticle ?? 2)}" />
            </label>
            <div class="form-hint muted">El CTA final del artículo es fijo: <strong>¿Comenzamos? · Contactar</strong>. El CTA temático va dentro del cuerpo.</div>
          </div>
          <label>Notas humanas<textarea name="notas_humanas" rows="2" placeholder="Restricciones, ángulo, enfoque"></textarea></label>
          <div class="actions">
            <button class="primary-button" type="submit">${iconSvg("spark")}Generar blog</button>
          </div>
        </form>

        <div class="panel">
          <h3>Blogs (${blogs.length})</h3>
          ${blogs.length ? blogsToolbar() : ""}
          <div class="blog-list" id="blogList">${
            blogs.length
              ? getFilteredBlogs().map((b) => blogListItem(b, selected?.id)).join("")
              : `<div class="empty">Aún no hay blogs generados.</div>`
          }</div>
        </div>
      </aside>

      <main class="blogs-main">
        ${selected ? blogDetail(selected) : `<div class="empty">Selecciona o genera un blog para verlo aquí.</div>`}
      </main>
    </div>
  `;
}

function blogSelect(name, label, options, defaultVal) {
  if (!options) return `<label>${escapeHtml(label)}<select name="${escapeAttr(name)}"><option>—</option></select></label>`;
  const opts = Object.entries(options).map(([k, v]) => {
    const text = typeof v === "string" ? v : (v.label || k);
    return `<option value="${escapeAttr(k)}" ${k === defaultVal ? "selected" : ""}>${escapeHtml(text)}</option>`;
  }).join("");
  return `<label>${escapeHtml(label)}<select name="${escapeAttr(name)}">${opts}</select></label>`;
}

function blogListItem(blog, selectedId) {
  const isSelected = blog.id === selectedId;
  const title = blog.title || blog.brief?.h1 || "(sin título)";
  const wc = blog.wordCount || blog.article?.word_count || 0;
  return `
    <button type="button" class="blog-list-item ${isSelected ? "is-selected" : ""}" data-action="blog-select" data-id="${escapeAttr(blog.id)}">
      <div class="blog-list-title">${escapeHtml(title)}</div>
      <div class="blog-list-meta">
        ${badge(statusLabels[blog.status] || blog.status, blog.status || "draft")}
        <span class="pill">${wc} palabras</span>
      </div>
    </button>
  `;
}

function blogDetail(blog) {
  const brief = blog.brief || {};
  const article = blog.article || {};
  const seo = blog.seo || {};
  const figures = blog.figures || [];
  const articleHtml = article.article_html_override || article.article_html || "";
  const renderedHtml = injectFigureImages(articleHtml, figures);

  return `
    <div class="blog-detail">
      <header class="blog-detail-head">
        <div>
          <div class="status-row">
            ${badge(statusLabels[blog.status] || blog.status, blog.status || "draft")}
            <span class="pill">${escapeHtml(brief.framework || "")}</span>
            <span class="pill">${escapeHtml(brief.search_intent || "")}</span>
            <span class="pill">${escapeHtml(brief.funnel_stage || "")}</span>
            <span class="pill">${article.word_count || 0} palabras</span>
          </div>
          <h2>${escapeHtml(blog.title || brief.h1 || "")}</h2>
          <p>${escapeHtml(brief.thought_leadership_angle || "")}</p>
        </div>
        <div class="blog-detail-actions">
          <button class="secondary-button" type="button" data-action="blog-copy-html" data-id="${escapeAttr(blog.id)}">${iconSvg("copy")}Copiar HTML</button>
          <button class="secondary-button" type="button" data-action="blog-download" data-id="${escapeAttr(blog.id)}">${iconSvg("upload")}Descargar HTML</button>
          <button class="primary-button" type="button" data-action="blog-status" data-status="ready" data-id="${escapeAttr(blog.id)}">${iconSvg("check")}Marcar listo</button>
          <button class="danger-button" type="button" data-action="blog-delete" data-id="${escapeAttr(blog.id)}">${iconSvg("trash")}Eliminar</button>
        </div>
      </header>

      <div class="blog-tabs">
        <button class="tab is-active" data-action="blog-tab" data-tab="preview" data-id="${escapeAttr(blog.id)}">Vista previa</button>
        <button class="tab" data-action="blog-tab" data-tab="seo" data-id="${escapeAttr(blog.id)}">SEO</button>
        <button class="tab" data-action="blog-tab" data-tab="brief" data-id="${escapeAttr(blog.id)}">Brief</button>
        <button class="tab" data-action="blog-tab" data-tab="figures" data-id="${escapeAttr(blog.id)}">Imágenes (${figures.length})</button>
      </div>

      <div class="blog-tab-content" data-tab-content="preview">
        <iframe class="blog-preview-frame" srcdoc="${escapeAttr(buildPreviewDocument(renderedHtml))}" sandbox="allow-same-origin"></iframe>
      </div>
      <div class="blog-tab-content hidden" data-tab-content="seo">
        ${blogSeoPanel(seo)}
      </div>
      <div class="blog-tab-content hidden" data-tab-content="brief">
        ${blogBriefPanel(brief)}
      </div>
      <div class="blog-tab-content hidden" data-tab-content="figures">
        ${blogFiguresPanel(blog.id, figures)}
      </div>
    </div>
  `;
}

function injectFigureImages(articleHtml, figures) {
  if (!articleHtml) return "";
  let out = articleHtml;
  for (const fig of figures) {
    if (!fig.image) continue;
    const id = fig.figure_id;
    const url = fig.image.displayUrl || fig.image.brandedUrl || fig.image.url;
    const re = new RegExp(`<figure([^>]*data-figure-id="${id}"[^>]*)>([\\s\\S]*?)</figure>`, "i");
    out = out.replace(re, (m, attrs, inner) => {
      return `<figure${attrs}><img src="${url}" alt="${escapeAttr(fig.caption || "")}" /><div class="fig-inner">${inner}</div></figure>`;
    });
  }
  return out;
}

function buildPreviewDocument(html) {
  return `<!doctype html><html lang="es"><head><meta charset="utf-8"><link rel="stylesheet" href="/blog-preview.css"></head><body>${html}</body></html>`;
}

async function buildStandaloneDocument(html, blog) {
  if (!app._blogPreviewCss) {
    try {
      const resp = await fetch("/blog-preview.css");
      app._blogPreviewCss = await resp.text();
    } catch {
      app._blogPreviewCss = "";
    }
  }
  const css = app._blogPreviewCss;
  const seo = blog?.seo || {};
  const title = seo.meta_title || blog?.title || "Blog Nexia GP";
  const description = seo.meta_description || "";
  const og = seo.open_graph || {};
  const schema = seo.schema_jsonld || "";
  const metaTags = [
    `<title>${escapeHtml(title)}</title>`,
    description ? `<meta name="description" content="${escapeAttr(description)}">` : "",
    og.og_title ? `<meta property="og:title" content="${escapeAttr(og.og_title)}">` : "",
    og.og_description ? `<meta property="og:description" content="${escapeAttr(og.og_description)}">` : "",
    og.og_type ? `<meta property="og:type" content="${escapeAttr(og.og_type)}">` : "",
    og.og_locale ? `<meta property="og:locale" content="${escapeAttr(og.og_locale)}">` : "",
    schema ? `<script type="application/ld+json">${schema}</script>` : "",
  ].filter(Boolean).join("\n  ");
  return `<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  ${metaTags}
  <style>
${css}
  </style>
</head>
<body>
${html}
</body>
</html>`;
}

function blogSeoPanel(seo) {
  if (!seo || !seo.meta_title) return `<div class="empty">Sin metadatos SEO.</div>`;
  return `
    <div class="seo-grid">
      ${kv("Meta title", seo.meta_title)}
      ${kv("Meta description", seo.meta_description)}
      ${kv("Slug", "/" + (seo.slug || ""))}
      ${kv("Canonical", seo.canonical_path)}
      ${kv("OG title", seo.open_graph?.og_title)}
      ${kv("OG description", seo.open_graph?.og_description)}
      ${kv("Densidad keyword (%)", seo.focus_keyphrase_density_estimate)}
      ${(seo.seo_review_flags || []).length ? `<div class="flag-list">${(seo.seo_review_flags || []).map((f) => `<span class="status-badge failed">${escapeHtml(f)}</span>`).join("")}</div>` : ""}
      <details>
        <summary>Schema.org JSON-LD</summary>
        <pre class="copy-block">${escapeHtml(seo.schema_jsonld || "")}</pre>
      </details>
    </div>
  `;
}

function blogBriefPanel(brief) {
  if (!brief || !brief.h1) return `<div class="empty">Sin brief.</div>`;
  return `
    <div class="brief-grid">
      ${kv("Persona", brief.target_persona)}
      ${kv("Tesis central", brief.core_thesis)}
      ${kv("Ángulo TL", brief.thought_leadership_angle)}
      ${kv("Keyword primaria", brief.primary_keyword)}
      ${kv("Secundarias", (brief.secondary_keywords || []).join(", "))}
      ${kv("Términos LSI", (brief.lsi_terms || []).join(", "))}
      ${kv("Lead magnet", brief.lead_magnet_suggestion?.title)}
      ${(brief.internal_links || []).length ? `<div class="kv"><span>Enlaces internos</span><div>${(brief.internal_links || []).map((l) => `<a href="${escapeAttr(l.url_path)}" target="_blank">${escapeHtml(l.anchor)}</a>`).join("<br/>")}</div></div>` : ""}
      ${(brief.notes_for_writer || []).length ? `<div class="kv"><span>Notas</span><div>${(brief.notes_for_writer || []).map((n) => `<p>${escapeHtml(n)}</p>`).join("")}</div></div>` : ""}
    </div>
  `;
}

function blogFiguresPanel(blogId, figures) {
  if (!figures.length) return `<div class="empty">Este blog no requiere imágenes.</div>`;
  return `<div class="figures-grid">${figures.map((f) => figureCard(blogId, f)).join("")}</div>`;
}

function figureCard(blogId, figure) {
  const id = escapeAttr(figure.figure_id);
  const hasImage = !!figure.image;
  const displayUrl = hasImage ? (figure.image.displayUrl || figure.image.brandedUrl || figure.image.url) : "";
  const blogCfg = (app.state.settings && app.state.settings.blog) || {};
  // Map settings.blog.imageQuality -> select value (the backend remaps low|standard|high -> low|medium|high).
  const cfgQualityToSelect = { low: "low", standard: "medium", high: "high" };
  const defaultQuality = cfgQualityToSelect[blogCfg.imageQuality || "standard"] || "medium";
  return `
    <div class="figure-card">
      <header>
        <strong>${escapeHtml(figure.figure_id)}</strong>
        <span class="pill">Sección ${figure.section_index}</span>
        ${hasImage ? badge(figure.image.config?.withFrame ? "Con marco" : "Sin marco", "published") : badge("Pendiente", "draft")}
      </header>
      ${hasImage ? `<img class="figure-thumb" src="${escapeAttr(displayUrl)}" alt="" loading="lazy" />` : `<div class="figure-placeholder">Pendiente de generar</div>`}
      <p class="copy-block">${escapeHtml(figure.image_prompt || "")}</p>
      <p class="figure-caption">${escapeHtml(figure.caption || "")}</p>
      <div class="figure-controls" id="figopts-${escapeAttr(blogId)}-${id}">
        <div class="two-cols">
          <label>Formato
            <select class="fig-size">
              <option value="1344x768">LinkedIn 16:9</option>
              <option value="1024x1024">Cuadrado</option>
              <option value="768x1344">Vertical</option>
            </select>
          </label>
          <label>Calidad
            <select class="fig-quality">
              <option value="low" ${defaultQuality === "low" ? "selected" : ""}>Ligera (barata)</option>
              <option value="medium" ${defaultQuality === "medium" ? "selected" : ""}>Estándar</option>
              <option value="high" ${defaultQuality === "high" ? "selected" : ""}>Alta</option>
            </select>
          </label>
        </div>
        <label class="switch-row"><span>Con marco corporativo (no recomendado para blog)</span><input type="checkbox" class="fig-frame" /></label>
        <label>Notas <textarea class="fig-notes" rows="2" placeholder="Opcional, ajustes al prompt"></textarea></label>
        <button class="primary-button" type="button" data-action="blog-figure-generate" data-blog="${escapeAttr(blogId)}" data-fig="${id}">${iconSvg("spark")}${hasImage ? "Regenerar" : "Generar"} imagen</button>
      </div>
    </div>
  `;
}

function renderLibrary() {
  document.getElementById("libraryView").innerHTML = `
    <div class="library-grid">
      <form class="panel form-grid" id="uploadForm" enctype="multipart/form-data">
        <label>Archivo<input name="file" type="file" required /></label>
        <label>Categoría
          <select name="category">
            <option value="nexia_core">Nexia core</option>
            <option value="web">Web</option>
            <option value="blog">Blog</option>
            <option value="fabricante">Fabricante</option>
            <option value="mercado">Mercado temporal</option>
            <option value="copywriting">Copywriting</option>
          </select>
        </label>
        <div class="actions">
          <button class="primary-button" type="submit">${iconSvg("upload")}Subir</button>
          <button class="secondary-button" type="button" data-action="import-local">${iconSvg("folder")}Importar local</button>
          <button class="ghost-button" type="button" data-action="sync-openai">${iconSvg("refresh")}Sincronizar OpenAI</button>
        </div>
        ${badge(app.state.settings.vectorStoreId || "Vector Store pendiente", app.state.settings.vectorStoreId ? "published" : "draft")}
      </form>
      <div class="panel">
        <h3>Fuentes cargadas</h3>
        ${app.state.files.length ? `<div class="file-list">${app.state.files.map(fileRow).join("")}</div>` : `<div class="empty">Sin archivos en la biblioteca.</div>`}
      </div>
    </div>
  `;
}

function renderStrategy() {
  const options = app.state.editorialOptions;
  const promptRows = Object.entries(options.postTypes)
    .filter(([id]) => id !== "auto")
    .map(([id, item]) => `
      <div class="prompt-card">
        <div class="prompt-card-head">
          <div>
            <h3>${escapeHtml(item.label)}</h3>
            <p>${escapeHtml(item.description)}</p>
          </div>
          <span class="pill">${escapeHtml(id)}</span>
        </div>
        <p class="copy-block">src/ai/prompts/post_types/${escapeHtml(id)}_v1.txt</p>
      </div>
    `)
    .join("");
  document.getElementById("strategyView").innerHTML = `
    <div class="work-grid">
      <div class="panel">
        <h3>Prompts base</h3>
        <div class="file-list">
          ${promptPath("Prompt base global", "src/ai/prompts/base_global_v1.txt")}
          ${promptPath("Planner", "src/ai/prompts/planner_v1.txt")}
          ${promptPath("Validator", "src/ai/prompts/validator_v1.txt")}
          ${promptPath("Adaptación X", "src/ai/prompts/transformers/adaptacion_x_v1.txt")}
          ${promptPath("Adaptación Facebook", "src/ai/prompts/transformers/adaptacion_facebook_v1.txt")}
        </div>
      </div>
      <div class="panel">
        <h3>7 prompts maestros</h3>
        <div class="prompt-list">${promptRows}</div>
      </div>
    </div>
  `;
}

function renderAutomation() {
  const settings = app.state.settings;
  document.getElementById("automationView").innerHTML = `
    <div class="settings-grid">
      <form class="panel form-grid" id="automationForm">
        <label class="switch-row"><span>Scheduler</span><input name="schedulerEnabled" type="checkbox" ${settings.schedulerEnabled ? "checked" : ""} /></label>
        <label>Cadencia en días<input name="cadenceDays" type="number" min="1" max="30" value="${escapeAttr(settings.cadenceDays || 3)}" /></label>
        ${selectField("defaultPostTypeId", "Tipo por defecto", editorialPostTypeOptions(), settings.defaultPostTypeId || "educativo_autoridad")}
        <label>Modo de salida
          <select name="publishMode">
            <option value="draft" ${settings.publishMode === "draft" ? "selected" : ""}>Borrador</option>
            <option value="ready" ${settings.publishMode === "ready" ? "selected" : ""}>Listo</option>
            <option value="auto" ${settings.publishMode === "auto" ? "selected" : ""}>Automático</option>
          </select>
        </label>
        <input type="hidden" name="model" value="${escapeAttr(settings.model || "")}" />
        <input type="hidden" name="vectorStoreId" value="${escapeAttr(settings.vectorStoreId || "")}" />
        <input type="hidden" name="vectorStoreName" value="${escapeAttr(settings.vectorStoreName || "")}" />
        <div class="actions">
          <button class="primary-button" type="submit">${iconSvg("save")}Guardar</button>
          <button class="secondary-button" type="button" data-action="scheduler-run">${iconSvg("clock")}Ejecutar ahora</button>
        </div>
      </form>
      <div class="panel">
        <h3>Historial</h3>
        ${app.state.schedulerLog.length ? `<div class="run-list">${app.state.schedulerLog.map(runRow).join("")}</div>` : `<div class="empty">Sin ejecuciones registradas.</div>`}
      </div>
    </div>
  `;
}

function renderSettings() {
  const host = document.getElementById("settingsView");
  if (!host) return;
  const tab = app.settingsTab || "general";
  const tabs = [
    { id: "general", label: "General" },
    { id: "posts", label: "Posts" },
    { id: "blog", label: "Blog" },
    { id: "prompts", label: "Prompts" },
  ];
  const navHtml = `
    <div class="settings-tabs">
      ${tabs.map((t) => `
        <button class="tab ${t.id === tab ? "is-active" : ""}" type="button" data-action="settings-tab" data-tab="${escapeAttr(t.id)}">
          ${escapeHtml(t.label)}
        </button>`).join("")}
    </div>`;
  let body = "";
  if (tab === "general") body = renderSettingsGeneralTab();
  else if (tab === "posts") body = renderSettingsPostsTab();
  else if (tab === "blog") body = renderSettingsBlogTab();
  else if (tab === "prompts") body = renderSettingsPromptsTab();
  host.innerHTML = `<div class="settings-shell">${navHtml}<div class="settings-body">${body}</div></div>`;
}

function renderSettingsGeneralTab() {
  const settings = app.state.settings || {};
  return `
    <div class="settings-grid">
      <form class="panel form-grid" id="settingsForm">
        <label>Modelo<input name="model" value="${escapeAttr(settings.model || "gpt-5.4-mini")}" /></label>
        <label>Vector Store ID<input name="vectorStoreId" value="${escapeAttr(settings.vectorStoreId || "")}" /></label>
        <label>Nombre Vector Store<input name="vectorStoreName" value="${escapeAttr(settings.vectorStoreName || "Nexia GP Knowledge Base")}" /></label>
        <div class="two-cols">
          <label>Cadencia<input name="cadenceDays" type="number" min="1" max="30" value="${escapeAttr(settings.cadenceDays || 3)}" /></label>
          ${selectField("defaultPostTypeId", "Tipo por defecto", editorialPostTypeOptions(), settings.defaultPostTypeId || "educativo_autoridad")}
        </div>
        <label>Modo de salida
          <select name="publishMode">
            <option value="draft" ${settings.publishMode === "draft" ? "selected" : ""}>Borrador</option>
            <option value="ready" ${settings.publishMode === "ready" ? "selected" : ""}>Listo</option>
            <option value="auto" ${settings.publishMode === "auto" ? "selected" : ""}>Automático</option>
          </select>
        </label>
        <label class="switch-row"><span>Scheduler</span><input name="schedulerEnabled" type="checkbox" ${settings.schedulerEnabled ? "checked" : ""} /></label>
        <button class="primary-button" type="submit">${iconSvg("save")}Guardar ajustes</button>
      </form>
      <div class="panel">
        <h3>Estado</h3>
        <div class="file-list">
          <div class="run-row"><strong>OpenAI</strong>${badge(app.state.hasOpenAIKey ? "Conectado" : "Sin clave", app.state.hasOpenAIKey ? "published" : "draft")}</div>
          <div class="run-row"><strong>Vector Store</strong>${badge(settings.vectorStoreId || "Pendiente", settings.vectorStoreId ? "published" : "draft")}</div>
          <div class="run-row"><strong>Publicación</strong>${badge(app.state.hasSocialWebhook ? "Webhook activo" : "Sin webhook", app.state.hasSocialWebhook ? "published" : "draft")}</div>
        </div>
      </div>
    </div>`;
}

function renderSettingsPostsTab() {
  const prompts = (app.state.prompts || []).filter((p) => p.scope === "posts");
  return `
    <div class="settings-grid">
      <div class="panel">
        <h3>Prompts de posts</h3>
        <p class="muted">Edita los prompts del pipeline editorial de posts desde la pestaña <a href="#" data-action="settings-tab" data-tab="prompts">Prompts</a>. Aquí abajo solo el resumen.</p>
        ${promptSummaryList(prompts)}
      </div>
      <div class="panel">
        <h3>Tipos de post</h3>
        <p class="muted">Los 7 tipos disponibles se gestionan desde la pestaña <a href="#strategy" data-nav="strategy">Temáticas</a>. Cada uno tiene su prompt maestro editable en Prompts.</p>
      </div>
    </div>`;
}

function renderSettingsBlogTab() {
  const blog = (app.state.settings && app.state.settings.blog) || {};
  const prompts = (app.state.prompts || []).filter((p) => p.scope === "blog");
  return `
    <div class="settings-grid">
      <form class="panel form-grid" id="settingsFormBlog">
        <h3>Configuración general del blog</h3>
        <label>Modelo por defecto<input name="defaultModel" value="${escapeAttr(blog.defaultModel || "gpt-5.4-mini")}" /></label>
        <div class="two-cols">
          <label>Longitud por defecto
            <select name="defaultLength">
              ${["corto", "medio", "largo"].map((v) => `<option value="${v}" ${blog.defaultLength === v ? "selected" : ""}>${escapeHtml(v)}</option>`).join("")}
            </select>
          </label>
          <label>Framework por defecto
            <select name="defaultFramework">
              ${["pas", "aida", "before_after_bridge", "stp", "fab"].map((v) => `<option value="${v}" ${blog.defaultFramework === v ? "selected" : ""}>${escapeHtml(v.toUpperCase())}</option>`).join("")}
            </select>
          </label>
        </div>
        <label>Audiencia por defecto<input name="defaultAudience" value="${escapeAttr(blog.defaultAudience || "fabricantes")}" /></label>
        <h3>Imágenes</h3>
        <p class="muted">Las imágenes de blog son ligeras: sin pase de edición, prompt corto, modelo barato. El objetivo es coste bajo por artículo.</p>
        <div class="two-cols">
          <label>Imágenes por artículo<input name="imagesPerArticle" type="number" min="0" max="6" value="${escapeAttr(blog.imagesPerArticle ?? 2)}" /></label>
          <label>Calidad de imagen
            <select name="imageQuality">
              ${["low", "standard", "high"].map((v) => `<option value="${v}" ${blog.imageQuality === v ? "selected" : ""}>${escapeHtml(v)}</option>`).join("")}
            </select>
          </label>
        </div>
        <label>Tope de coste por artículo (céntimos)<input name="costTargetCents" type="number" min="0" max="1000" value="${escapeAttr(blog.costTargetCents ?? 30)}" /></label>
        <button class="primary-button" type="submit">${iconSvg("save")}Guardar ajustes de blog</button>
      </form>
      <div class="panel">
        <h3>Prompts de blog</h3>
        <p class="muted">Estos son los prompts que usa el pipeline de blog. Edítalos desde la pestaña <a href="#" data-action="settings-tab" data-tab="prompts">Prompts</a>.</p>
        ${promptSummaryList(prompts)}
      </div>
    </div>`;
}

function renderSettingsPromptsTab() {
  const prompts = app.state.prompts || [];
  if (!prompts.length) {
    return `<div class="empty">No hay prompts registrados.</div>`;
  }
  if (app.editingPromptId) {
    if (!app.editingPromptDetail || app.editingPromptDetail.id !== app.editingPromptId) {
      return `<div class="panel"><div class="empty">Cargando prompt…</div></div>`;
    }
    return renderPromptEditor(app.editingPromptDetail);
  }
  const groups = {};
  prompts.forEach((p) => {
    if (!groups[p.group]) groups[p.group] = [];
    groups[p.group].push(p);
  });
  const groupOrder = ["core_posts", "post_types", "transformers", "blog"];
  const sections = groupOrder
    .filter((g) => groups[g])
    .map((g) => `
      <div class="panel">
        <h3>${escapeHtml(PROMPT_GROUP_LABELS[g] || g)}</h3>
        ${promptSummaryList(groups[g])}
      </div>`)
    .join("");
  return `<div class="settings-grid">${sections}</div>`;
}

function promptSummaryList(rows) {
  if (!rows || !rows.length) return `<div class="empty">Sin prompts en este grupo.</div>`;
  return `<div class="prompt-table">
    ${rows.map((p) => `
      <div class="prompt-table-row">
        <div class="prompt-table-main">
          <strong>${escapeHtml(p.label)}</strong>
          <span class="muted">${escapeHtml(p.id)}</span>
        </div>
        <div class="prompt-table-meta">
          <span class="pill ${p.source === "user" ? "is-warn" : ""}">${p.source === "user" ? "Editado" : "Por defecto"}</span>
          <span class="muted">v${p.versionCount || 1}</span>
        </div>
        <button class="ghost-button" type="button" data-action="prompt-open" data-id="${escapeAttr(p.id)}">${iconSvg("edit") || ""}Editar</button>
      </div>`).join("")}
  </div>`;
}

function renderPromptEditor(detail) {
  const history = (detail.history || []).slice().reverse(); // newest first
  return `
    <div class="prompt-editor">
      <div class="prompt-editor-head">
        <button class="ghost-button" type="button" data-action="prompt-close">← Volver</button>
        <div class="prompt-editor-title">
          <h3>${escapeHtml(detail.label)}</h3>
          <span class="muted">${escapeHtml(detail.id)}</span>
        </div>
        <div class="prompt-editor-actions">
          <span class="pill ${detail.source === "user" ? "is-warn" : ""}">${detail.source === "user" ? "Editado" : "Por defecto"}</span>
          <button class="ghost-button" type="button" data-action="prompt-history-toggle">${iconSvg("clock") || ""}Histórico (${history.length})</button>
        </div>
      </div>
      <div class="prompt-editor-body">
        <form id="promptEditorForm" data-id="${escapeAttr(detail.id)}" class="prompt-editor-form">
          <textarea name="text" rows="22" spellcheck="false" required>${escapeHtml(detail.text || "")}</textarea>
          <div class="prompt-editor-foot">
            <input name="note" placeholder="Nota opcional sobre el cambio (qué tocas y por qué)" maxlength="160" />
            <button class="primary-button" type="submit">${iconSvg("save")}Guardar como nueva versión</button>
          </div>
        </form>
        ${app.promptHistoryOpen ? renderPromptHistory(detail, history) : ""}
      </div>
    </div>`;
}

function renderPromptHistory(detail, history) {
  if (!history.length) {
    return `<aside class="prompt-history"><div class="empty">Sin histórico aún. Al guardar la primera edición se registrará la baseline más tu cambio.</div></aside>`;
  }
  return `
    <aside class="prompt-history">
      <h4>Histórico</h4>
      <div class="prompt-history-list">
        ${history.map((v) => `
          <div class="prompt-history-row">
            <div>
              <strong>v${v.version}</strong>
              <span class="pill">${escapeHtml(v.source || "user")}</span>
            </div>
            <div class="muted">${escapeHtml(formatTimestamp(v.createdAt))}</div>
            ${v.note ? `<p class="prompt-history-note">${escapeHtml(v.note)}</p>` : ""}
            <button class="ghost-button" type="button" data-action="prompt-revert" data-id="${escapeAttr(detail.id)}" data-version="${escapeAttr(String(v.version))}">Restaurar v${v.version}</button>
          </div>`).join("")}
      </div>
    </aside>`;
}

function formatTimestamp(value) {
  if (!value) return "";
  try {
    return new Date(value).toLocaleString("es-ES", { dateStyle: "short", timeStyle: "short" });
  } catch (e) {
    return value;
  }
}

function selectField(name, label, options, selected) {
  return `
    <label>${escapeHtml(label)}
      <select name="${escapeAttr(name)}">
        ${Object.entries(options)
          .map(([value, item]) => {
            const text = typeof item === "string" ? item : item.label || value;
            return `<option value="${escapeAttr(value)}" ${value === selected ? "selected" : ""}>${escapeHtml(text)}</option>`;
          })
          .join("")}
      </select>
    </label>
  `;
}

function editorialPostTypeOptions() {
  const entries = Object.entries(app.state.editorialOptions.postTypes).filter(([id]) => id !== "auto");
  return Object.fromEntries(entries);
}

function latestSummary(post) {
  return `
    <div class="latest-summary">
      <h3>Última generación</h3>
      ${kv("Ángulo", post.brief?.core_angle)}
      ${kv("Confianza", post.generation?.traceability?.confidence)}
      ${kv("Fuentes", (post.retrieval?.sources || []).map((s) => s.title).join(", "))}
    </div>
  `;
}

function step(title, text) {
  return `<div class="pipeline-step"><strong>${escapeHtml(title)}</strong><span>${escapeHtml(text)}</span></div>`;
}

function sourceList(sources) {
  if (!sources.length) return `<div class="empty">Sin fuentes trazadas.</div>`;
  return `<div class="source-list">${sources
    .map(
      (source) => `
        <div class="source-card">
          <div class="source-card-head">
            <strong>${escapeHtml(source.title)}</strong>
            <span class="pill">${escapeHtml(source.source_group)}</span>
          </div>
          <p>${escapeHtml(source.excerpt)}</p>
        </div>
      `,
    )
    .join("")}</div>`;
}

function flagList(flags) {
  if (!flags.length) return `<div class="risk-ok">${iconSvg("check")}<span>Sin flags críticos</span></div>`;
  return `<div class="flag-list">${flags.map((flag) => `<span class="status-badge failed">${escapeHtml(flag)}</span>`).join("")}</div>`;
}

function adaptationBlocks(postId, adaptations) {
  if (!adaptations) return `<div class="empty">Sin adaptaciones todavía.</div>`;
  return `
    <div class="adapt-grid">
      <div class="channel-card">
        <div class="channel-card-head"><strong>X</strong><button class="icon-button" type="button" data-action="copy-adaptation" data-channel="x" data-id="${escapeAttr(postId)}" title="Copiar X">${iconSvg("copy")}</button></div>
        <p class="copy-block emphasis">${escapeHtml(adaptations.x?.short_version || "")}</p>
        ${(adaptations.x?.thread || []).map((item, index) => `<p class="thread-item"><span>${index + 1}</span>${escapeHtml(item)}</p>`).join("")}
      </div>
      <div class="channel-card">
        <div class="channel-card-head"><strong>Facebook</strong><button class="icon-button" type="button" data-action="copy-adaptation" data-channel="facebook" data-id="${escapeAttr(postId)}" title="Copiar Facebook">${iconSvg("copy")}</button></div>
        <p class="copy-block">${escapeHtml(adaptations.facebook?.final_post || "")}</p>
      </div>
    </div>
  `;
}

function reviewStat(label, value) {
  return `<div class="review-stat"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`;
}

function hookOption(label, value) {
  return `
    <div class="hook-card">
      <span>${escapeHtml(label)}</span>
      <p>${escapeHtml(value || "")}</p>
    </div>
  `;
}

function fileRow(file) {
  const statusClass = file.status === "failed" ? "failed" : file.status === "completed" ? "published" : "draft";
  return `
    <div class="file-row">
      <div class="file-row-main">
        <div>
          <h3>${escapeHtml(file.name)}</h3>
          <div class="file-meta">
            ${badge(file.status, statusClass)}
            <span class="pill">${escapeHtml(file.category)}</span>
            <span class="pill">${formatBytes(file.size)}</span>
          </div>
        </div>
        <button class="danger-button" type="button" data-action="file-delete" data-id="${escapeAttr(file.id)}">${iconSvg("trash")}Eliminar</button>
      </div>
      ${file.error ? `<p class="copy-block">${escapeHtml(file.error)}</p>` : ""}
    </div>
  `;
}

function runRow(run) {
  return `
    <div class="run-row">
      <div>
        <strong>${formatDate(run.createdAt)}</strong>
        <div class="card-meta"><span class="pill">${escapeHtml(run.source)}</span><span class="pill">${run.generated} posts</span></div>
      </div>
      ${run.errors?.length ? badge(`${run.errors.length} errores`, "failed") : badge("OK", "published")}
    </div>
  `;
}

function promptPath(label, path) {
  return `<div class="run-row"><strong>${escapeHtml(label)}</strong><span class="pill">${escapeHtml(path)}</span></div>`;
}

function kv(label, value) {
  return `<div class="kv"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value || "Pendiente")}</strong></div>`;
}

function metric(label, value) {
  return `<div class="metric"><span>${escapeHtml(label)}</span><strong>${Number(value || 0)}</strong></div>`;
}

function badge(text, status) {
  return `<span class="status-badge ${escapeAttr(status || "")}">${escapeHtml(text || "")}</span>`;
}

function labelFor(group, key) {
  const item = app.state.editorialOptions?.[group]?.[key];
  if (!item) return key || "";
  return typeof item === "string" ? item : item.label || key;
}

async function api(url, options = {}) {
  return fetchJson(url, {
    headers: { "content-type": "application/json", ...(options.headers || {}) },
    ...options,
  });
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok || data.ok === false) throw new Error(data.error || "Error de la petición");
  return data;
}

async function withLoading(button, task) {
  if (!button) return task();
  button.disabled = true;
  button.classList.add("loading");
  try {
    return await task();
  } finally {
    button.disabled = false;
    button.classList.remove("loading");
  }
}

function findPost(id) {
  return app.state.posts.find((post) => post.id === id);
}

function formatFinalPost(post) {
  if (!post) return "";
  const copy = post.generation?.copy || {};
  return [copy.final_post || post.copy, copy.cta || post.cta, (copy.hashtags || post.hashtags || []).join(" ")]
    .filter(Boolean)
    .join("\n\n");
}

function getAdaptationText(post, channel) {
  if (!post?.adaptations) return "";
  if (channel === "x") {
    const x = post.adaptations.x || {};
    return [x.short_version, x.alternative, ...(x.thread || [])].filter(Boolean).join("\n\n");
  }
  const fb = post.adaptations.facebook || {};
  return [fb.final_post, fb.cta].filter(Boolean).join("\n\n");
}

function toast(message, isError = false) {
  const host = document.getElementById("toast");
  host.textContent = message;
  host.style.background = isError ? "#7a2119" : "";
  host.classList.add("is-visible");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => host.classList.remove("is-visible"), 3400);
}

function formatDate(value) {
  if (!value) return "Pendiente";
  return new Intl.DateTimeFormat("es-ES", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

function formatBytes(bytes) {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** index).toFixed(index ? 1 : 0)} ${units[index]}`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttr(value) {
  return escapeHtml(value);
}

function injectStaticIcons() {
  document.querySelectorAll("[data-icon]").forEach((node) => {
    node.innerHTML = iconSvg(node.dataset.icon);
  });
}

function imageSection(post) {
  const img = post.image;
  const id = escapeAttr(post.id);

  const displayUrl = img?.brandedUrl || img?.url || "";
  const hasBranded = !!img?.brandedUrl;
  const withFrame = img?.config?.withFrame ?? img?.cloudinary?.withFrame;
  const existingImage = img ? `
    <div class="generated-image-wrap">
      <img class="generated-image" src="${escapeAttr(displayUrl)}" alt="Imagen generada para el post" loading="lazy" />
      <div class="image-meta">
        ${hasBranded ? `<span class="status-badge published">${withFrame ? "Con marco" : "Sin marco"}</span>` : `<span class="status-badge draft">Local</span>`}
        <span class="pill">${escapeHtml(img.config?.size || "")}</span>
        <span class="pill">${escapeHtml(img.config?.quality || "")}</span>
        <span class="pill">${escapeHtml(img.config?.style || "")}</span>
      </div>
      <details class="image-prompt-detail">
        <summary>Ver prompt generado</summary>
        <p class="copy-block">${escapeHtml(img.prompt || "")}</p>
      </details>
    </div>
  ` : "";

  const toggleLabel = img ? "Regenerar imagen" : "Generar imagen con IA";

  return `
    <section class="review-panel image-section">
      <div class="image-section-head">
        <div class="section-label compact">
          <span>${iconSvg("image")}</span>
          <h3>Imagen</h3>
        </div>
        <button class="secondary-button small" type="button" data-action="image-panel-toggle" data-id="${id}">
          ${iconSvg("spark")}${escapeHtml(toggleLabel)}
        </button>
      </div>

      ${existingImage}

      <div class="image-gen-options" id="img-opts-${id}" style="display:none">
        <div class="two-cols">
          <label>Formato
            <select class="img-size">
              <option value="1344x768">LinkedIn apaisado (16:9)</option>
              <option value="1024x1024">Cuadrado (1:1)</option>
              <option value="768x1344">Vertical (9:16)</option>
            </select>
          </label>
          <label>Calidad
            <select class="img-quality">
              <option value="medium">Media</option>
              <option value="high">Alta</option>
              <option value="low">Rápida (baja)</option>
            </select>
          </label>
        </div>
        <label>Estilo visual
          <select class="img-style">
            <option value="Fotografía documental editorial, estilo reportaje profesional">Documental editorial</option>
            <option value="Fotografía corporativa auténtica, momentos reales sin poses">Corporativa auténtica</option>
            <option value="Fotografía industrial y logística, maquinaria y operaciones reales">Industrial / logística</option>
            <option value="Fotografía de entorno mediterráneo canario, paisaje y luz atlántica">Entorno canario</option>
          </select>
        </label>
        <label class="switch-row">
          <span>Con marco corporativo <span class="field-hint">(franja borrosa + línea chocolate + logo)</span></span>
          <input type="checkbox" class="img-frame" checked />
        </label>
        <label>Notas para la imagen <span class="field-hint">(opcional — la IA generará el prompt)</span>
          <textarea class="img-notes" rows="2" placeholder="Ej: incluir entorno portuario, tonos cálidos, perspectiva aérea..."></textarea>
        </label>
        <button class="primary-button" type="button" data-action="generate-image" data-id="${id}">
          ${iconSvg("spark")}Generar imagen
        </button>
      </div>
    </section>
  `;
}

function iconSvg(name) {
  const paths = {
    spark: '<path d="M12 2l1.6 5.2L19 9l-5.4 1.8L12 16l-1.6-5.2L5 9l5.4-1.8L12 2z"/><path d="M5 14l.8 2.7L8.5 18l-2.7.8L5 22l-.8-3.2L1.5 18l2.7-1.3L5 14z"/>',
    layout: '<path d="M3 4h18v5H3z"/><path d="M3 13h7v7H3z"/><path d="M14 13h7v7h-7z"/>',
    folder: '<path d="M3 6h7l2 2h9v11H3z"/><path d="M3 10h18"/>',
    target: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4"/><path d="M12 2v4M12 18v4M2 12h4M18 12h4"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v6l4 2"/>',
    settings: '<path d="M12 8a4 4 0 100 8 4 4 0 000-8z"/><path d="M4 12h2M18 12h2M12 4v2M12 18v2M6.3 6.3l1.4 1.4M16.3 16.3l1.4 1.4M17.7 6.3l-1.4 1.4M7.7 16.3l-1.4 1.4"/>',
    refresh: '<path d="M20 6v6h-6"/><path d="M4 18v-6h6"/><path d="M18 9a7 7 0 00-11.8-2.5L4 9"/><path d="M6 15a7 7 0 0011.8 2.5L20 15"/>',
    alert: '<path d="M12 3l10 18H2L12 3z"/><path d="M12 9v5M12 17h.01"/>',
    copy: '<rect x="8" y="8" width="11" height="11" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V5a2 2 0 012-2h8a2 2 0 012 2v1"/>',
    check: '<path d="M20 6L9 17l-5-5"/>',
    send: '<path d="M22 2L11 13"/><path d="M22 2l-7 20-4-9-9-4 20-7z"/>',
    undo: '<path d="M9 14L4 9l5-5"/><path d="M4 9h10a6 6 0 010 12h-2"/>',
    trash: '<path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M6 6l1 15h10l1-15"/><path d="M10 11v6M14 11v6"/>',
    upload: '<path d="M12 16V4"/><path d="M7 9l5-5 5 5"/><path d="M4 20h16"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    save: '<path d="M5 3h12l2 2v16H5z"/><path d="M8 3v6h8V3"/><path d="M8 21v-7h8v7"/>',
    image: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/>',
    article: '<path d="M4 4h12l4 4v12H4z"/><path d="M16 4v4h4"/><path d="M8 12h8"/><path d="M8 16h8"/><path d="M8 8h4"/>',
  };
  return `<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${paths[name] || paths.spark}</svg>`;
}
