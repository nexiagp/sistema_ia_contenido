const app = {
  state: null,
  view: location.hash?.replace("#", "") || "generator",
  busy: false,
  settingsTab: "general",       // general | posts | blog | prompts
  editingPromptId: null,
  editingPromptDetail: null,
  promptHistoryOpen: false,
  jobs: { editorial: null, blog: null },
  fileFilters: { status: "all", q: "" },
  activeBlogReviewTab: "seo",
  calendarType: "posts",
  calendarSelection: null,
  calendarAgendaView: "month",
  calendarMonth: null,
  calendarSelectedDay: null,
  auth: null,
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
  calendar: "Calendario editorial",
  automation: "Automatización",
  settings: "Ajustes",
};

const statusLabels = {
  draft: "Borrador",
  review: "En revisión",
  ready: "Listo",
  published: "Publicado",
  scheduled: "Programado",
};

document.addEventListener("DOMContentLoaded", async () => {
  if (!(await initializeProtectedSession())) return;
  injectStaticIcons();
  bindEvents();
  await loadState();
});

async function initializeProtectedSession() {
  const config = await fetchJson("/api/auth/config");
  app.auth = config;
  if (!config.required) return true;
  if (!config.configured) {
    renderAuthGate("El acceso protegido aún no está configurado. Completa las variables de entorno seguras antes de abrir la aplicación.");
    return false;
  }

  const fragment = new URLSearchParams(location.hash.replace(/^#/, ""));
  const accessToken = fragment.get("access_token");
  if (accessToken && config.mode === "supabase") {
    try {
      await establishProtectedSession(accessToken);
      history.replaceState(null, "", `${location.pathname}${location.search}`);
    } catch (error) {
      renderAuthGate(error.message || "No ha sido posible validar el acceso.");
      return false;
    }
  }

  if (await hasProtectedSession()) {
    document.body.classList.remove("auth-blocked");
    return true;
  }
  renderAuthGate();
  return false;
}

async function establishProtectedSession(accessToken) {
  const response = await fetch("/api/auth/session", {
    method: "POST",
    credentials: "same-origin",
    headers: { authorization: `Bearer ${accessToken}` },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || data.ok === false) throw new Error(data.error || "No se ha podido iniciar sesión.");
  app.auth.user = data.user;
}

async function hasProtectedSession() {
  const response = await fetch("/api/auth/session", { credentials: "same-origin" });
  if (!response.ok) return false;
  const data = await response.json().catch(() => ({}));
  app.auth.user = data.user;
  return data.ok === true;
}

function renderAuthGate(message = "") {
  document.body.classList.add("auth-blocked");
  const gate = document.getElementById("authGate");
  if (!gate) return;
  gate.hidden = false;
  const passwordMode = app.auth?.mode === "password";
  gate.innerHTML = `
    <div class="auth-card">
      <img src="/logo-web.png" alt="Nexia Growth Partner" class="auth-logo" />
      <p class="eyebrow">Área privada</p>
      <h1>Nexia GP Content</h1>
      <p>${passwordMode ? "Introduce la contraseña del equipo para acceder." : "Introduce tu correo autorizado. Te enviaremos un enlace seguro de acceso."}</p>
      <form id="authLoginForm" class="auth-form">
        <label>${passwordMode ? "Contraseña del equipo" : "Correo autorizado"}
          ${passwordMode
            ? '<input name="password" type="password" autocomplete="current-password" required />'
            : '<input name="email" type="email" autocomplete="email" required placeholder="nombre@empresa.com" />'}
        </label>
        <button class="primary-button" type="submit">${passwordMode ? "Entrar" : "Enviar enlace de acceso"}</button>
      </form>
      <p class="auth-message ${message ? "is-error" : ""}" id="authMessage">${escapeHtml(message)}</p>
    </div>`;
  gate.querySelector("#authLoginForm")?.addEventListener("submit", passwordMode ? requestTeamPassword : requestMagicLink);
}

async function requestTeamPassword(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const password = String(new FormData(form).get("password") || "");
  const message = document.getElementById("authMessage");
  const button = form.querySelector("button[type='submit']");
  if (!password) return;
  button.disabled = true;
  try {
    const response = await fetch("/api/auth/password", {
      method: "POST",
      credentials: "same-origin",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ password }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || data.ok === false) throw new Error(data.error || "No se ha podido iniciar sesión.");
    location.reload();
  } catch (error) {
    message.classList.add("is-error");
    message.textContent = error.message || "No se ha podido iniciar sesión.";
    button.disabled = false;
  }
}

async function requestMagicLink(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const email = String(new FormData(form).get("email") || "").trim();
  const message = document.getElementById("authMessage");
  const button = form.querySelector("button[type='submit']");
  if (!email || !app.auth?.url || !app.auth?.publishableKey) return;
  button.disabled = true;
  try {
    const redirect = `${location.origin}/`;
    const response = await fetch(`${app.auth.url}/auth/v1/otp?redirect_to=${encodeURIComponent(redirect)}`, {
      method: "POST",
      headers: {
        apikey: app.auth.publishableKey,
        authorization: `Bearer ${app.auth.publishableKey}`,
        "content-type": "application/json",
      },
      body: JSON.stringify({ email, create_user: false, data: {} }),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.msg || error.message || "No se ha podido solicitar el acceso.");
    }
    message.classList.remove("is-error");
    message.textContent = "Revisa tu correo y abre el enlace de acceso. Puede tardar unos segundos.";
  } catch (error) {
    message.classList.add("is-error");
    message.textContent = error.message || "No se ha podido solicitar el acceso.";
  } finally {
    button.disabled = false;
  }
}

async function handleAuthenticationExpired() {
  if (!app.auth?.required) return;
  await fetch("/api/auth/logout", { method: "POST", credentials: "same-origin" }).catch(() => undefined);
  renderAuthGate(app.auth?.mode === "password"
    ? "La sesión ha caducado. Introduce de nuevo la contraseña del equipo."
    : "La sesión ha caducado. Solicita un nuevo enlace de acceso.");
}

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
    if (event.target.id === "filesSearch") {
      app.fileFilters = app.fileFilters || { status: "all", q: "" };
      app.fileFilters.q = event.target.value;
      renderLibraryList();
    }
  });

  document.addEventListener("click", async (event) => {
    const nav = event.target.closest("[data-nav]");
    if (nav) {
      setView(nav.dataset.nav);
      closeMobileNav();
      return;
    }

    const action = event.target.closest("[data-action]");
    if (!action) return;

    try {
      const name = action.dataset.action;

      if (name === "mobile-nav-toggle") {
        toggleMobileNav();
        return;
      }

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
        const post = findPost(action.dataset.id);
        const payload = { status: action.dataset.status };
        if (action.dataset.status === "ready" && qualityReviewRequired(post)) {
          if (!confirm(qualityReviewMessage(post?.qualityGate, "post"))) return;
          payload.reviewAcknowledged = true;
        }
        await withLoading(action, () =>
          api(`/api/posts/${action.dataset.id}`, {
            method: "PATCH",
            body: JSON.stringify(payload),
          }),
        );
        await loadState("Estado actualizado");
      }

      if (name === "post-publish") {
        const post = findPost(action.dataset.id);
        if (post?.status !== "scheduled" || !post?.editorialApprovedAt || !post?.scheduledFor) {
          toast("Aprueba el post y prográmalo antes de publicarlo.", true);
          return;
        }
        if (new Date(post.scheduledFor).getTime() > Date.now()) {
          toast("El post se podrá enviar al llegar la fecha programada.", true);
          return;
        }
        if (!app.state?.hasSocialWebhook) {
          toast("La publicación automática no está conectada. Marca el post como listo para revisión.", true);
          return;
        }
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

      if (name === "post-image-open") {
        event.preventDefault();
        event.stopPropagation();
        const review = action.closest(".editorial-review")?.querySelector(".post-review-details");
        if (review) review.open = true;
        const manager = document.getElementById(`img-manager-${action.dataset.id}`);
        if (manager) manager.open = true;
        const section = action.closest(".editorial-review")?.querySelector(".visual-workbench");
        requestAnimationFrame(() => section?.scrollIntoView({ behavior: "smooth", block: "start" }));
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

      if (name === "files-filter") {
        app.fileFilters = app.fileFilters || { status: "all", q: "" };
        app.fileFilters.status = action.dataset.status || "all";
        renderLibraryList();
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

      if (name === "image-preview") {
        const post = findPost(action.dataset.id);
        const image = post?.image;
        const displayUrl = image?.displayUrl || image?.brandedUrl || image?.url;
        const dialog = document.getElementById("imagePreviewDialog");
        const body = document.getElementById("imagePreviewBody");
        if (!displayUrl || !dialog || !body) return;
        body.innerHTML = `
          <img src="${escapeAttr(displayUrl)}" alt="Imagen generada para el post" />
          <p>${escapeHtml(post.title || post.brief?.core_angle || "Imagen editorial")}</p>`;
        if (typeof dialog.showModal === "function") dialog.showModal();
        else window.open(displayUrl, "_blank", "noopener");
        return;
      }

      if (name === "blog-figure-preview") {
        const blog = (app.state?.blogs || []).find((item) => item.id === action.dataset.blog);
        const figure = (blog?.figures || []).find((item) => item.figure_id === action.dataset.fig);
        const image = figure?.image;
        const displayUrl = image?.displayUrl || image?.brandedUrl || image?.url;
        const dialog = document.getElementById("imagePreviewDialog");
        const body = document.getElementById("imagePreviewBody");
        if (!displayUrl || !dialog || !body) return;
        body.innerHTML = `<img src="${escapeAttr(displayUrl)}" alt="${escapeAttr(figure.caption || "Imagen del artículo")}" /><p>${escapeHtml(figure.caption || `Imagen ${figure.figure_id || "del artículo"}`)}</p>`;
        if (typeof dialog.showModal === "function") dialog.showModal();
        else window.open(displayUrl, "_blank", "noopener");
        return;
      }

      if (name === "image-download") {
        const imageUrl = action.dataset.url;
        if (!imageUrl) {
          toast("No hay un PNG disponible para descargar", true);
          return;
        }
        await withLoading(action, () => downloadImagePng(imageUrl, action.dataset.filename || "imagen-nexia.png"));
        toast("PNG descargado en calidad original");
        return;
      }

      if (name === "image-preview-close") {
        document.getElementById("imagePreviewDialog")?.close();
        return;
      }

      if (name === "image-panel-toggle") {
        const manager = document.getElementById(`img-manager-${action.dataset.id}`);
        if (manager) {
          manager.open = !manager.open;
          action.classList.toggle("is-active", manager.open);
        }
        return;
      }

      if (name === "visual-option-select") {
        const panel = action.closest(".image-gen-options");
        const field = action.dataset.field;
        const input = panel?.querySelector(field === "direction" ? ".img-direction" : ".img-composition");
        if (!panel || !input || !field) return;
        input.value = action.dataset.value || "";
        panel.querySelectorAll(`[data-action='visual-option-select'][data-field='${field}']`).forEach((option) => {
          const active = option === action;
          option.classList.toggle("is-selected", active);
          option.setAttribute("aria-pressed", String(active));
        });
        return;
      }

      if (name === "generate-image") {
        const postId = action.dataset.id;
        const panel = document.getElementById(`img-opts-${postId}`);
        const size = panel?.querySelector(".img-size")?.value || "1536x1024";
        const quality = panel?.querySelector(".img-quality")?.value || "medium";
        const direction = panel?.querySelector(".img-direction")?.value || "operacion_real";
        const composition = panel?.querySelector(".img-composition")?.value || "contexto_amplio";
        const userNotes = panel?.querySelector(".img-notes")?.value || "";
        const withFrame = panel?.querySelector(".img-frame")?.checked ?? true;
        const withLogo = panel?.querySelector(".img-logo")?.checked ?? withFrame;
        await withLoading(action, () =>
          api(`/api/posts/${postId}/generate-image`, {
            method: "POST",
            body: JSON.stringify({ size, quality, direction, composition, userNotes, withFrame, withLogo }),
          }),
        );
        await loadState("Concepto visual generado");
        return;
      }

      if (name === "image-variant-select") {
        const postId = action.dataset.id;
        const imageId = action.dataset.image;
        await withLoading(action, () => api(`/api/posts/${postId}/images/${imageId}/select`, { method: "POST" }));
        await loadState("Concepto visual activo");
        return;
      }

      if (name === "image-review") {
        const postId = action.dataset.id;
        const imageId = action.dataset.image;
        await withLoading(action, () =>
          api(`/api/posts/${postId}/images/${imageId}/review`, {
            method: "POST",
            body: JSON.stringify({ approved: true }),
          }),
        );
        await loadState("Imagen aprobada por revisión humana");
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

      if (name === "manufacturer-web-sync" || name === "manufacturer-x-sync") {
        const includeX = name === "manufacturer-x-sync";
        await withLoading(action, () =>
          api(`/api/manufacturer-sources/${encodeURIComponent(action.dataset.id)}/sync`, {
            method: "POST",
            body: JSON.stringify({ syncX: includeX, syncWeb: !includeX }),
          }),
        );
        await loadState(includeX ? "Consulta de X terminada" : "Web del fabricante actualizada");
        return;
      }

      if (name === "manufacturer-website-toggle") {
        const enabled = action.dataset.enabled !== "true";
        await withLoading(action, () =>
          api(`/api/manufacturer-sources/${encodeURIComponent(action.dataset.id)}`, {
            method: "PATCH",
            body: JSON.stringify({ websiteEnabled: enabled }),
          }),
        );
        await loadState(enabled ? "Fuente web activada" : "Fuente web pausada");
        return;
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
        const review = action.closest(".blog-review-inspector");
        app.activeBlogReviewTab = tab;
        review?.querySelectorAll(".blog-tabs .tab").forEach((t) => {
          const active = t.dataset.tab === tab;
          t.classList.toggle("is-active", active);
          t.setAttribute("aria-selected", String(active));
        });
        review?.querySelectorAll("[data-tab-content]").forEach((content) => {
          content.classList.toggle("hidden", content.dataset.tabContent !== tab);
        });
        requestAnimationFrame(() => review?.scrollIntoView({ behavior: "smooth", block: "start" }));
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
        const blog = (app.state.blogs || []).find((item) => item.id === action.dataset.id);
        const payload = { status: action.dataset.status };
        if (action.dataset.status === "ready" && qualityReviewRequired(blog)) {
          if (!confirm(qualityReviewMessage(blog?.qualityGate, "blog", "aprobarlo para WordPress"))) return;
          payload.reviewAcknowledged = true;
        }
        await withLoading(action, () =>
          api(`/api/blogs/${action.dataset.id}`, {
            method: "PATCH",
            body: JSON.stringify(payload),
          }),
        );
        await loadState(action.dataset.status === "ready" ? "Contenido aprobado para WordPress" : "Estado actualizado");
        return;
      }

      if (name === "blog-wordpress-sync") {
        const blog = (app.state.blogs || []).find((item) => item.id === action.dataset.id);
        if (!isBlogApprovedForWordPress(blog)) {
          toast("Aprueba primero el contenido para WordPress.", true);
          return;
        }
        if (qualityReviewRequired(blog)) {
          toast("Registra antes la revisión editorial al aprobar el contenido.", true);
          return;
        }
        if (!confirm("Se creará o actualizará un BORRADOR en WordPress. No se publicará ningún artículo. ¿Continuar?")) return;
        await withLoading(action, () =>
          api(`/api/blogs/${action.dataset.id}/wordpress/draft`, { method: "POST", body: "{}" }),
        );
        await loadState("Borrador de WordPress creado o actualizado");
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
        const size = panel?.querySelector(".fig-size")?.value || "1536x1024";
        const quality = panel?.querySelector(".fig-quality")?.value || "medium";
        const direction = panel?.querySelector(".fig-direction")?.value || "territorio_infraestructura";
        const composition = panel?.querySelector(".fig-composition")?.value || "contexto_amplio";
        const withFrame = panel?.querySelector(".fig-frame")?.checked ?? false;
        const withLogo = panel?.querySelector(".fig-logo")?.checked ?? withFrame;
        const userNotes = panel?.querySelector(".fig-notes")?.value || "";
        await withLoading(action, () =>
          api(`/api/blogs/${blogId}/figures/${figId}/generate-image`, {
            method: "POST",
            body: JSON.stringify({ size, quality, direction, composition, withFrame, withLogo, userNotes }),
          }),
        );
        await loadState("Imagen generada");
        return;
      }

      if (name === "scheduler-run") {
        await withLoading(action, () => api("/api/scheduler/run", { method: "POST" }));
        await loadState("Automatización ejecutada");
      }

      if (name === "calendar-type-select") {
        app.calendarType = action.dataset.kind === "blogs" ? "blogs" : "posts";
        app.calendarSelection = null;
        renderCalendar();
        return;
      }

      if (name === "calendar-item-select") {
        app.calendarSelection = { kind: action.dataset.kind, id: action.dataset.id };
        renderCalendar();
        return;
      }

      if (name === "calendar-selection-clear") {
        app.calendarSelection = null;
        renderCalendar();
        return;
      }

      if (name === "calendar-agenda-view") {
        app.calendarAgendaView = action.dataset.view === "list" ? "list" : "month";
        renderCalendar();
        return;
      }

      if (name === "calendar-month-change") {
        app.calendarMonth = calendarShiftMonth(action.dataset.direction === "previous" ? -1 : 1);
        app.calendarSelectedDay = null;
        renderCalendar();
        return;
      }

      if (name === "calendar-day-select") {
        app.calendarSelectedDay = action.dataset.date || null;
        renderCalendar();
        return;
      }

      if (name === "calendar-schedule" || name === "calendar-reschedule") {
        const host = action.closest(name === "calendar-schedule" ? ".calendar-programming" : ".calendar-card");
        const selectedDate = host?.querySelector(".calendar-date")?.value || "";
        const kind = action.dataset.kind;
        const id = action.dataset.id;
        if (!selectedDate) {
          toast("Selecciona día y hora antes de añadir la pieza al calendario.", true);
          return;
        }
        const label = await scheduleCalendarItem(kind, id, selectedDate, action);
        if (!label) return;
        app.calendarSelection = null;
        await loadState(`${label} añadido al calendario`);
        return;
      }

      if (name === "post-schedule") {
        const card = action.closest(".calendar-card");
        const selectedDate = card?.querySelector(".calendar-date")?.value || "";
        if (!selectedDate) {
          toast("Selecciona fecha y hora antes de planificar el post.", true);
          return;
        }
        const scheduledFor = new Date(selectedDate).toISOString();
        const post = findPost(action.dataset.id);
        if (post?.status !== "ready" && post?.status !== "scheduled") {
          toast("Aprueba el post antes de programarlo.", true);
          return;
        }
        const payload = { scheduledFor };
        if (qualityReviewRequired(post)) {
          if (!confirm(qualityReviewMessage(post?.qualityGate, "post"))) return;
          payload.reviewAcknowledged = true;
        }
        await withLoading(action, () =>
          api(`/api/posts/${action.dataset.id}`, {
            method: "PATCH",
            body: JSON.stringify(payload),
          }),
        );
        await loadState("Post planificado para revisión editorial");
        return;
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
        await runGenerationJob("editorial", payload, form.querySelector("button[type='submit']"));
        return;
      }

      if (form.id === "blogForm") {
        const payload = Object.fromEntries(new FormData(form));
        await runGenerationJob("blog", payload, form.querySelector("button[type='submit']"));
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

      if (form.classList.contains("manufacturer-source-form")) {
        const data = new FormData(form);
        await withLoading(form.querySelector("button[type='submit']"), () =>
          api(`/api/manufacturer-sources/${encodeURIComponent(form.dataset.id)}`, {
            method: "PATCH",
            body: JSON.stringify({
              xHandle: data.get("xHandle") || "",
              xEnabled: data.get("xEnabled") === "on",
            }),
          }),
        );
        await loadState("Configuración del fabricante guardada");
        return;
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

async function runGenerationJob(kind, payload, button) {
  if (app.jobs[kind]?.status === "running" || app.jobs[kind]?.status === "queued") {
    toast("Ya hay una generación en curso para este flujo.", true);
    return;
  }
  const originalLabel = button?.innerHTML;
  if (button) {
    button.disabled = true;
    button.classList.add("loading");
  }
  try {
    const started = await api(`/api/jobs/${kind}`, { method: "POST", body: JSON.stringify(payload) });
    app.jobs[kind] = started.job;
    renderGenerationProgress(kind);
    const job = await pollGenerationJob(kind, started.job.id);
    if (job.status === "failed") throw new Error(job.error || "La generación no se ha completado.");
    app.jobs[kind] = null;
    if (kind === "blog") app.selectedBlogId = job.resultId || null;
    await loadState(kind === "blog" ? "Blog generado y preparado para revisión" : "Pipeline editorial completado");
    setView(kind === "blog" ? "blogs" : "posts");
  } finally {
    if (button) {
      button.disabled = false;
      button.classList.remove("loading");
      if (originalLabel) button.innerHTML = originalLabel;
    }
  }
}

async function pollGenerationJob(kind, jobId) {
  for (;;) {
    const response = await fetchJson(`/api/jobs/${encodeURIComponent(jobId)}`);
    app.jobs[kind] = response.job;
    renderGenerationProgress(kind);
    if (response.job.status === "completed" || response.job.status === "failed") return response.job;
    await new Promise((resolve) => setTimeout(resolve, 800));
  }
}

function generationProgress(kind) {
  const job = app.jobs?.[kind];
  return `<div id="generation-progress-${kind}">${job ? generationProgressCard(job) : ""}</div>`;
}

function renderGenerationProgress(kind) {
  const host = document.getElementById(`generation-progress-${kind}`);
  if (host) host.innerHTML = app.jobs?.[kind] ? generationProgressCard(app.jobs[kind]) : "";
}

function generationProgressCard(job) {
  const stateLabel = job.status === "queued" ? "En cola" : job.status === "completed" ? "Completado" : job.status === "failed" ? "Error" : "En curso";
  return `
    <section class="generation-progress ${escapeAttr(job.status)}" aria-live="polite">
      <div class="generation-progress-head">
        <div><p class="eyebrow">Generación en vivo</p><h3>${escapeHtml(stateLabel)}</h3></div>
        <span class="status-badge ${job.status === "failed" ? "failed" : job.status === "completed" ? "published" : "draft"}">${escapeHtml(stateLabel)}</span>
      </div>
      <p>${escapeHtml(job.error || job.message || "Preparando…")}</p>
      <ol class="generation-progress-steps">
        ${(job.steps || []).map((step) => `<li class="is-${escapeAttr(step.status)}"><span>${step.status === "completed" ? "✓" : step.status === "running" ? "…" : ""}</span>${escapeHtml(step.label)}</li>`).join("")}
      </ol>
    </section>`;
}

function toggleMobileNav() {
  const sidebar = document.getElementById("appSidebar");
  const button = document.querySelector("[data-action='mobile-nav-toggle']");
  if (!sidebar || !button) return;
  const open = sidebar.classList.toggle("is-mobile-open");
  button.setAttribute("aria-expanded", String(open));
}

function closeMobileNav() {
  const sidebar = document.getElementById("appSidebar");
  const button = document.querySelector("[data-action='mobile-nav-toggle']");
  sidebar?.classList.remove("is-mobile-open");
  button?.setAttribute("aria-expanded", "false");
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
  renderCalendar();
  renderAutomation();
  renderSettings();
  updateView();
}

function setView(view) {
  app.view = view;
  closeMobileNav();
  updateView();
  history.replaceState(null, "", `#${view}`);
  window.scrollTo(0, 0);
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
    ${generationProgress("editorial")}
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
        ${chip("review", "En revisión")}
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

function imageDownloadFilename(value) {
  const stem = String(value || "imagen-nexia")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
  return `${stem || "imagen-nexia"}.png`;
}

async function downloadImagePng(url, filename) {
  // Se descarga el binario entregado por el servicio de imagen: no hay canvas,
  // miniatura ni recodificación, así que se conserva el PNG final original.
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error("No se ha podido recuperar la imagen para descargarla");
  const blob = await response.blob();
  if (!blob.size) throw new Error("La imagen descargada está vacía");
  if (blob.type && blob.type !== "image/png") throw new Error("El archivo disponible no está en formato PNG");

  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = imageDownloadFilename(filename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
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
  const instagram = (ad.instagram || {}).caption || "";
  const instagramTags = (ad.instagram || {}).hashtags || [];
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
          <div class="cp-head"><span class="cp-avatar">NGP</span><div class="cp-id"><strong>Nexia GP</strong><small>@NexiaGP</small></div><span class="cp-logo">X</span></div>
          <div class="cp-body">${xText ? nl(xText) : "<em>Sin adaptación a X</em>"}</div>
          ${xText ? `<div class="cp-meta ${xOver ? "cp-over" : "cp-ok"}">${xText.length}/280${xOver ? " · excede" : ""}</div>` : ""}
        </div>
        <div class="cp-card cp-fb">
          <div class="cp-head"><span class="cp-avatar">NGP</span><div class="cp-id"><strong>Nexia Growth Partner</strong><small>Facebook</small></div><span class="cp-logo">f</span></div>
          <div class="cp-body">${fb ? nl(fb) : "<em>Sin adaptación a Facebook</em>"}</div>
          ${fb ? `<div class="cp-meta">${fb.length} caracteres</div>` : ""}
        </div>
        <div class="cp-card cp-instagram">
          <div class="cp-head"><span class="cp-avatar">NGP</span><div class="cp-id"><strong>Nexia Growth Partner</strong><small>Instagram · perfil pendiente</small></div><span class="cp-logo">◎</span></div>
          <div class="cp-body">${instagram ? nl(instagram) : "<em>Sin adaptación a Instagram</em>"}</div>
          ${instagramTags.length ? `<div class="cp-tags">${instagramTags.map((tag) => `<span>${escapeHtml(tag)}</span>`).join(" ")}</div>` : ""}
          ${instagram ? `<div class="cp-meta">${instagram.length} caracteres · imagen por aprobar</div>` : ""}
        </div>
      </div>
    </div>`;
}

function contentPiecePreview(post) {
  const copy = post.generation?.copy || {};
  const finalPost = copy.final_post || post.copy || "";
  const tags = copy.hashtags || post.hashtags || [];
  const image = post.image;
  const imageUrl = image?.displayUrl || image?.brandedUrl || image?.url || "";
  const variants = retainedImageVariants(post).length;
  const visualLabel = image?.config?.direction ? labelForVisual("directions", image.config.direction) : "Sin dirección visual";
  const compositionLabel = image?.config?.composition ? labelForVisual("compositions", image.config.composition) : "Elige el encuadre";
  const media = image
    ? `<button class="post-visual-thumb" type="button" data-action="image-preview" data-id="${escapeAttr(post.id)}" aria-label="Ampliar imagen de la pieza">
        <img src="${escapeAttr(imageUrl)}" alt="Vista de la imagen para el post" loading="lazy" />
        <span>${iconSvg("expand")}Ver a tamaño completo</span>
      </button>`
    : `<button class="post-visual-empty" type="button" data-action="post-image-open" data-id="${escapeAttr(post.id)}">
        <span>${iconSvg("image")}</span>
        <strong>Falta la pieza visual</strong>
        <small>Elige qué debe contar la imagen y crea una primera propuesta.</small>
        <em>Crear imagen</em>
      </button>`;
  const copyBody = app.editingPostId === post.id
    ? `<div class="desk-copy-editing">
        <label class="edit-label">Copy para LinkedIn<textarea class="edit-copy" rows="10">${escapeHtml(finalPost)}</textarea></label>
        <div class="desk-copy-fields">
          <label class="edit-label">Hashtags<input class="edit-hashtags" value="${escapeAttr(tags.join(" "))}" /></label>
          <label class="edit-label">CTA<input class="edit-cta" value="${escapeAttr(copy.cta || post.cta || "")}" /></label>
        </div>
        <div class="actions">
          <button class="primary-button" type="button" data-action="post-edit-save" data-id="${escapeAttr(post.id)}">${iconSvg("check")}Guardar cambios</button>
          <button class="ghost-button" type="button" data-action="post-edit-cancel" data-id="${escapeAttr(post.id)}">Cancelar</button>
        </div>
      </div>`
    : `<div class="desk-copy-reading">
        <p>${escapeHtml(finalPost)}</p>
        <div class="desk-copy-meta">
          <span>${finalPost.trim().length} caracteres</span>
          ${copy.cta || post.cta ? `<span>CTA · ${escapeHtml(copy.cta || post.cta)}</span>` : ""}
        </div>
        ${tags.length ? `<div class="desk-copy-tags">${tags.map((tag) => `<span>${escapeHtml(tag)}</span>`).join(" ")}</div>` : ""}
        <div class="actions desk-copy-actions">
          <button class="primary-button" type="button" data-action="copy-final" data-id="${escapeAttr(post.id)}">${iconSvg("copy")}Copiar post</button>
          <button class="secondary-button" type="button" data-action="post-edit" data-id="${escapeAttr(post.id)}">${iconSvg("layout")}Editar copy</button>
          <button class="ghost-button" type="button" data-action="channel-preview-toggle" data-id="${escapeAttr(post.id)}">${iconSvg("layout")}Comparar canales</button>
        </div>
        ${channelPreview(post)}
      </div>`;
  return `
    <section class="post-editorial-desk" aria-label="Mesa de revisión de la pieza">
      <section class="desk-copy-panel">
        <header class="desk-panel-head">
          <div><p class="eyebrow">Copy final</p><h3>Texto de LinkedIn</h3></div>
          <span class="platform-chip">in&nbsp; LinkedIn</span>
        </header>
        ${copyBody}
      </section>
      <aside class="desk-visual-panel">
        <header class="desk-panel-head">
          <div><p class="eyebrow">Pieza visual</p><h3>${escapeHtml(image ? "Imagen seleccionada" : "Aún sin imagen")}</h3></div>
          ${image?.review?.status === "approved" ? badge("Revisada", "published") : badge(image ? "Por revisar" : "Pendiente", "draft")}
        </header>
        ${media}
        <div class="visual-glance-grid">
          <div><span>Qué comunica</span><strong>${escapeHtml(visualLabel)}</strong></div>
          <div><span>Cómo se encuadra</span><strong>${escapeHtml(compositionLabel)}</strong></div>
        </div>
        <div class="visual-glance-footer">
          <span>${image ? `${variants} ${variants === 1 ? "concepto" : "conceptos"}` : "Sin concepto generado"}</span>
          <div class="visual-glance-actions">
            ${imageUrl ? `<button class="ghost-button small image-download-button" type="button" data-action="image-download" data-url="${escapeAttr(imageUrl)}" data-filename="${escapeAttr(imageDownloadFilename(`${post.title || post.brief?.core_angle || "post-nexia"}-imagen`))}">${iconSvg("download")}Descargar PNG</button>` : ""}
            <button class="secondary-button small" type="button" data-action="post-image-open" data-id="${escapeAttr(post.id)}">
              ${iconSvg(image ? "image" : "spark")}${image ? "Gestionar imagen" : "Crear imagen"}
            </button>
          </div>
        </div>
      </aside>
    </section>`;
}

function postVisualGlance(post) {
  const image = post.image;
  const imageUrl = image?.displayUrl || image?.brandedUrl || image?.url || "";
  if (!image) {
    return `<div class="review-visual-glance is-empty">
      <span>${iconSvg("image")}</span>
      <div><strong>Sin imagen</strong><small>Abre la pieza para crearla</small></div>
    </div>`;
  }
  const variants = retainedImageVariants(post).length;
  const direction = labelForVisual("directions", image.config?.direction) || "Imagen editorial";
  return `<div class="review-visual-glance">
    <img src="${escapeAttr(imageUrl)}" alt="Miniatura de la imagen del post" loading="lazy" />
    <div><strong>${escapeHtml(direction)}</strong><small>${variants} ${variants === 1 ? "concepto" : "conceptos"} · abrir para ampliar</small></div>
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
  const finalPost = copy.final_post || post.copy || "";
  const summaryText = finalPost.replace(/\s+/g, " ").trim();
  const compactSummary = summaryText.length > 185 ? `${summaryText.slice(0, 182).trimEnd()}…` : summaryText;
  return `
    <article class="editorial-review">
      <details class="post-review-details" ${app.editingPostId === post.id ? "open" : ""}>
      <summary class="review-hero">
        <div class="review-title-block">
          <div class="status-row">
            ${badge(statusLabels[post.status] || post.status || "Borrador", post.status || "draft")}
            ${badge(labelFor("postTypes", brief.post_type), "published")}
            ${badge(labelFor("audiences", brief.audience), "")}
            ${badge(post.provider || "pipeline", "")}
            ${qualityGateBadge(post.qualityGate)}
          </div>
          <h3>${escapeHtml(brief.core_angle || post.title || "Post editorial")}</h3>
          <p>${escapeHtml(compactSummary || brief.core_thesis || post.idea || "")}</p>
        </div>
          <div class="review-summary-aside">
            <div class="review-scoreboard">
              ${reviewStat("Fuentes", sourceCount)}
              ${reviewStat("Palabras", wordCount)}
              ${reviewStat("Riesgo", validation.risk_level || "low")}
              ${reviewStat("Flags", (validation.review_flags || []).length)}
            </div>
            ${postVisualGlance(post)}
            <span class="review-expand">Ver pieza ${iconSvg("chevron")}</span>
        </div>
      </summary>

      <div class="post-review-expanded">
      ${contentPiecePreview(post)}
      ${imageSection(post)}
      <details class="review-disclosure review-control-disclosure">
        <summary><span>${iconSvg("check")}Control editorial</span><small>brief, riesgo y aprobación</small></summary>
        <div class="review-support-grid review-control-grid">
          <section class="review-panel">${approvalChecklist(post)}</section>
          <section class="review-panel">
            <div class="section-label compact"><span>${iconSvg("target")}</span><h3>Brief y revisión</h3></div>
            ${kv("Por qué importa", brief.why_it_matters)}
            ${kv("CTA", brief.cta_type)}
            ${kv("Sensibilidad", brief.factual_sensitivity)}
            ${flagList(validation.review_flags || [])}
            ${kv("Revisión humana", validation.human_review_required ? "Sí" : "Normal")}
            ${qualityGateNotice(post.qualityGate)}
            ${(validation.validation_notes || []).map((note) => `<p class="note-line">${escapeHtml(note)}</p>`).join("")}
          </section>
        </div>
      </details>

      <details class="review-disclosure">
        <summary><span>${iconSvg("spark")}Ideas y reutilización</span><small>hooks, reactivación y visual</small></summary>
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
      </details>

      <details class="review-disclosure">
        <summary><span>${iconSvg("folder")}Fuentes usadas (${sourceCount})</span><small>trazabilidad y fragmentos</small></summary>
        <section class="review-panel">${sourceList(retrieval.sources || [])}</section>
      </details>

      <details class="review-disclosure">
        <summary><span>${iconSvg("send")}Adaptaciones multicanal</span><small>X, Facebook e Instagram</small></summary>
        <section class="review-panel">${adaptationBlocks(post.id, adaptations)}</section>
      </details>

      <footer class="review-actions">
        <button class="ghost-button" type="button" data-action="regenerate" data-id="${escapeAttr(post.id)}" data-instruction="Hazlo menos promocional y mas basado en criterio de mercado.">${iconSvg("undo")}Menos promocional</button>
        <button class="ghost-button" type="button" data-action="regenerate" data-id="${escapeAttr(post.id)}" data-instruction="Hazlo mas util, con una lectura practica mas clara.">${iconSvg("target")}Más útil</button>
        <button class="ghost-button" type="button" data-action="regenerate" data-id="${escapeAttr(post.id)}" data-instruction="Hazlo mas corto sin perder la idea central.">${iconSvg("layout")}Más corto</button>
        <button class="secondary-button" type="button" data-action="post-status" data-status="ready" data-id="${escapeAttr(post.id)}">${iconSvg("check")}Aprobar para calendario</button>
        ${app.state?.hasSocialWebhook
          ? `<button class="primary-button" type="button" data-action="post-publish" data-id="${escapeAttr(post.id)}">${iconSvg("send")}Publicar</button>`
          : `<span class="publish-unavailable" title="Conecta el webhook social antes de enviar publicaciones">${iconSvg("alert")}Publicación automática no conectada</span>`}
        <button class="danger-button" type="button" data-action="post-delete" data-id="${escapeAttr(post.id)}">${iconSvg("trash")}Eliminar</button>
      </footer>
      </div>
      </details>
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
    ${generationProgress("blog")}
    <div class="blogs-template-bar">
      <div class="blogs-template-info">
        <strong>Plantilla activa:</strong>
        <span class="pill">longitud ${escapeHtml(blogCfg.defaultLength || "medio")}</span>
        <span class="pill">framework ${escapeHtml((blogCfg.defaultFramework || "pas").toUpperCase())}</span>
        <span class="pill">${blogCfg.imagesPerArticle ?? 2} imágenes (${escapeHtml(cfgImageQualityLabel)}, sin marco)</span>
        <span class="pill">CTA fija "¿Comenzamos? · Contactar"</span>
      </div>
      <div class="blogs-template-actions">
        <span class="muted">${counts.blogs || 0} totales · ${counts.blogsDraft || 0} borradores · ${counts.blogsReview || 0} en revisión · ${counts.blogsReady || 0} listos · ${counts.blogsPublished || 0} publicados</span>
        <button class="ghost-button" type="button" data-action="settings-tab" data-tab="blog">${iconSvg("settings")}Ajustes de Blog</button>
      </div>
    </div>

    <div class="blogs-workbench">
      <details class="blog-composer" ${blogs.length ? "" : "open"}>
        <summary>
          <div>
            <p class="eyebrow">Nuevo artículo</p>
            <h3>Crear un blog con criterio editorial y SEO</h3>
            <p>Define la tesis y las restricciones antes de generar; los artículos ya creados quedan ordenados justo debajo.</p>
          </div>
          <span class="blog-composer-trigger">${iconSvg("spark")}Crear blog</span>
        </summary>
        <form class="panel form-grid blog-composer-form" id="blogForm">
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
      </details>

      <section class="blog-catalogue" aria-label="Artículos creados">
        <header class="blog-catalogue-head">
          <div><p class="eyebrow">Artículos creados</p><h3>Elige un blog para revisar y preparar</h3></div>
          <span>${blogs.length} ${blogs.length === 1 ? "artículo" : "artículos"}</span>
        </header>
          ${blogs.length ? blogsToolbar() : ""}
          <div class="blog-list" id="blogList">${
            blogs.length
              ? getFilteredBlogs().map((b) => blogListItem(b, selected?.id)).join("")
              : `<div class="empty">Aún no hay blogs generados.</div>`
          }</div>
      </section>

      <main class="blogs-main" aria-live="polite">
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
      <span class="blog-list-card-mark">${iconSvg("article")}</span>
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
  const activeTab = ["seo", "brief", "figures"].includes(app.activeBlogReviewTab) ? app.activeBlogReviewTab : "seo";
  const wordpress = blog.wordpress || {};
  const wordpressConfigured = !!app.state?.wordpress?.configured;
  const approvedForWordPress = isBlogApprovedForWordPress(blog);
  const wordpressDraftExists = Boolean(wordpress.postId && wordpress.postUrl);
  const wordpressSyncAvailable = wordpressConfigured && approvedForWordPress;
  const approvalControl = approvedForWordPress
    ? `<span class="blog-handoff-confirmed">${iconSvg("check")}Contenido aprobado</span>`
    : `<button class="primary-button" type="button" data-action="blog-status" data-status="ready" data-id="${escapeAttr(blog.id)}">${iconSvg("check")}Aprobar contenido</button>`;
  const wordpressControl = wordpressSyncAvailable
    ? `<button class="primary-button" type="button" data-action="blog-wordpress-sync" data-id="${escapeAttr(blog.id)}" title="${wordpressDraftExists ? "Actualiza el borrador existente; no publica" : "Crea un borrador; no publica"}">${iconSvg("upload")}${wordpressDraftExists ? "Actualizar borrador WordPress" : "Crear borrador en WordPress"}</button>`
    : `<button class="secondary-button" type="button" disabled title="${wordpressConfigured ? "Aprueba primero el contenido para WordPress" : "Configura WordPress en el servidor para activar esta acción"}">${iconSvg("upload")}Crear borrador en WordPress</button>`;
  const calendarMessage = blog.scheduledFor
    ? `Agenda editorial reservada para ${formatDate(blog.scheduledFor)}.`
    : "Reserva la fecha desde Calendario cuando el equipo haya validado el plan.";
  const wordpressError = wordpress.lastError
    ? `<small class="blog-handoff-note is-error">Último intento WordPress: ${escapeHtml(wordpress.lastError)}</small>`
    : wordpressDraftExists
      ? `<small class="blog-handoff-note">Borrador de WordPress · ${escapeHtml(wordpress.status || "draft")} · ${escapeHtml(formatTimestamp(wordpress.lastSyncAt))}</small>`
      : `<small class="blog-handoff-note">${wordpressConfigured ? "Siempre crea un borrador; nunca publica el artículo." : "WordPress aún no está configurado en el servidor."}</small>`;
  const rankMath = wordpress.rankMath || {};
  const rankMathApplied = Array.isArray(rankMath.applied) ? rankMath.applied : [];
  const rankMathMessage = wordpressDraftExists
    ? rankMathApplied.length
      ? `Rank Math aplicado: ${rankMathApplied.map((field) => ({ rank_math_title: "metatítulo", rank_math_description: "metadescripción", rank_math_focus_keyword: "keyword" }[field] || field)).join(", ")}.`
      : "Rank Math: revisa metatítulo, metadescripción y keyword antes de publicar."
    : "Rank Math se completará automáticamente si sus campos están disponibles por API; si no, quedará señalado para revisión.";

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
            ${wordpress.postUrl ? badge("Borrador WordPress", "ready") : ""}
            ${qualityGateBadge(blog.qualityGate)}
          </div>
          <h2>${escapeHtml(blog.title || brief.h1 || "")}</h2>
          <p>${escapeHtml(brief.thought_leadership_angle || "")}</p>
        </div>
        <div class="blog-detail-actions">
          <button class="secondary-button" type="button" data-action="blog-copy-html" data-id="${escapeAttr(blog.id)}">${iconSvg("copy")}Copiar HTML</button>
          <button class="secondary-button" type="button" data-action="blog-download" data-id="${escapeAttr(blog.id)}">${iconSvg("upload")}Descargar HTML</button>
          <button class="danger-button" type="button" data-action="blog-delete" data-id="${escapeAttr(blog.id)}">${iconSvg("trash")}Eliminar</button>
        </div>
      </header>

      <section class="blog-handoff" aria-label="Flujo de publicación del blog">
        <header class="blog-handoff-head">
          <div><p class="eyebrow">Flujo de publicación</p><h3>Del visto bueno al borrador de la web</h3></div>
          <p>La agenda organiza el plan editorial. Nunca publica por sí sola.</p>
        </header>
        <ol class="blog-handoff-steps">
          <li class="blog-handoff-step ${approvedForWordPress ? "is-complete" : "is-current"}">
            <span class="blog-handoff-index" aria-hidden="true">1</span>
            <div class="blog-handoff-copy"><span>Revisión editorial</span><h4>Aprobar contenido</h4><p>Registra la revisión y deja el artículo listo para enviarlo.</p></div>
            <div class="blog-handoff-action">${approvalControl}</div>
          </li>
          <li class="blog-handoff-step ${wordpressDraftExists ? "is-complete" : approvedForWordPress ? "is-current" : "is-waiting"}">
            <span class="blog-handoff-index" aria-hidden="true">2</span>
            <div class="blog-handoff-copy"><span>WordPress</span><h4>${wordpressDraftExists ? "Borrador creado" : "Crear borrador"}</h4><p>Inserta el artículo y sus imágenes en la plantilla actual de la web. ${escapeHtml(rankMathMessage)}</p></div>
            <div class="blog-handoff-action">${wordpressControl}${wordpressDraftExists ? `<a class="secondary-button" href="${escapeAttr(wordpress.editUrl || wordpress.postUrl)}" target="_blank" rel="noopener">${iconSvg("expand")}Abrir borrador</a>` : ""}${wordpressError}</div>
          </li>
          <li class="blog-handoff-step ${blog.scheduledFor ? "is-complete" : "is-waiting"}">
            <span class="blog-handoff-index" aria-hidden="true">3</span>
            <div class="blog-handoff-copy"><span>Agenda editorial</span><h4>Reservar fecha</h4><p>Coordina la publicación cada 15 días desde el calendario del equipo.</p></div>
            <div class="blog-handoff-action"><small class="blog-handoff-note">${escapeHtml(calendarMessage)}</small><small class="blog-handoff-note">La programación final se revisa manualmente en WordPress.</small></div>
          </li>
        </ol>
      </section>

      <section class="article-preview-stage" aria-label="Vista previa del artículo">
        <header class="article-preview-stage-head">
          <div><p class="eyebrow">Vista previa del artículo</p><h3>Lectura final antes de prepararlo</h3></div>
          <span>${article.word_count || 0} palabras · ${figures.length} ${figures.length === 1 ? "imagen" : "imágenes"}</span>
        </header>
        <iframe class="blog-preview-frame" title="Vista previa de ${escapeAttr(blog.title || brief.h1 || "artículo")}" srcdoc="${escapeAttr(buildPreviewDocument(renderedHtml))}" sandbox="allow-same-origin"></iframe>
      </section>

      <section class="blog-review-inspector" aria-label="Control editorial del artículo">
        <header class="blog-review-inspector-head">
          <div><p class="eyebrow">Control editorial</p><h3>Comprueba la base antes de preparar el artículo</h3></div>
          <span>El artículo sigue visible arriba</span>
        </header>
        <div class="blog-tabs" role="tablist" aria-label="Aspecto a revisar">
          <button class="tab ${activeTab === "seo" ? "is-active" : ""}" type="button" role="tab" aria-selected="${activeTab === "seo"}" data-action="blog-tab" data-tab="seo" data-id="${escapeAttr(blog.id)}">SEO y resultado</button>
          <button class="tab ${activeTab === "brief" ? "is-active" : ""}" type="button" role="tab" aria-selected="${activeTab === "brief"}" data-action="blog-tab" data-tab="brief" data-id="${escapeAttr(blog.id)}">Enfoque editorial</button>
          <button class="tab ${activeTab === "figures" ? "is-active" : ""}" type="button" role="tab" aria-selected="${activeTab === "figures"}" data-action="blog-tab" data-tab="figures" data-id="${escapeAttr(blog.id)}">Imágenes (${figures.length})</button>
        </div>

        <div class="blog-tab-content ${activeTab === "seo" ? "" : "hidden"}" data-tab-content="seo">
          ${blogSeoPanel(blog, seo)}
        </div>
        <div class="blog-tab-content ${activeTab === "brief" ? "" : "hidden"}" data-tab-content="brief">
          ${blogBriefPanel(brief)}
        </div>
        <div class="blog-tab-content ${activeTab === "figures" ? "" : "hidden"}" data-tab-content="figures">
          ${blogFiguresPanel(blog.id, figures)}
        </div>
      </section>
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
  const schema = safeJsonLdForExport(seo.schema_jsonld);
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

function friendlySeoFlag(flag) {
  const labels = {
    keyword_density_high: "La keyword principal aparece con demasiada frecuencia; revisa repeticiones antes de preparar el artículo.",
    keyword_density_low: "La keyword principal aparece poco; revisa si el texto responde con claridad a la búsqueda.",
    meta_title_length: "El título de buscador merece una revisión de longitud.",
    meta_description_length: "La descripción de buscador merece una revisión de longitud.",
  };
  return labels[flag] || String(flag || "Revisión SEO pendiente").replace(/_/g, " ");
}

function friendlyBriefValue(group, value) {
  const labels = {
    intent: {
      informational: "Resolver una búsqueda informativa",
      commercial: "Evaluar una solución o proveedor",
      transactional: "Tomar una decisión de contacto",
      navigational: "Encontrar una página concreta",
    },
    funnel: {
      tofu: "Descubrimiento · TOFU",
      mofu: "Consideración · MOFU",
      bofu: "Decisión · BOFU",
    },
  };
  return labels[group]?.[value] || value || "Pendiente";
}

function parseSchemaJson(raw) {
  try {
    const schema = JSON.parse(raw || "{}");
    return schema && typeof schema === "object" ? schema : {};
  } catch {
    return {};
  }
}

function blogSeoPanel(blog, seo) {
  if (!seo || !seo.meta_title) return `<div class="empty">Este artículo aún no tiene una ficha SEO generada.</div>`;
  const gate = blog.qualityGate || {};
  const seoFlags = seo.seo_review_flags || [];
  const otherBlockers = (gate.blockers || []).filter((message) => !seoFlags.some((flag) => String(message).includes(flag)));
  const flags = [...seoFlags.map(friendlySeoFlag), ...otherBlockers];
  const warnings = gate.warnings || [];
  const path = seo.canonical_path || `/${seo.slug || ""}`;
  const schema = parseSchemaJson(seo.schema_jsonld);
  const schemaType = schema["@type"] || "Article";
  const schemaAuthor = typeof schema.author === "object" ? schema.author?.name : schema.author;
  const schemaPublisher = typeof schema.publisher === "object" ? schema.publisher?.name : schema.publisher;
  const datePublished = schema.datePublished === "AUTO" ? "Se completa al publicar" : (schema.datePublished || "Pendiente");
  const density = seo.focus_keyphrase_density_estimate != null ? `${seo.focus_keyphrase_density_estimate}%` : "Pendiente";
  return `
    <div class="seo-review-board">
      <section class="seo-readiness ${flags.length ? "needs-review" : "is-ready"}">
        <span class="seo-readiness-icon">${iconSvg(flags.length ? "alert" : "check")}</span>
        <div>
          <p class="eyebrow">Preparación para calendario</p>
          <h4>${flags.length ? "Hay un punto que revisar" : "SEO listo para revisión final"}</h4>
          <p>${flags.length ? "El artículo no se pierde ni se bloquea: esta es la comprobación concreta antes de marcarlo como listo." : "La ficha de buscador, la URL y los datos estructurados no muestran bloqueos."}</p>
          ${flags.length ? `<ul>${flags.map((flag) => `<li>${escapeHtml(flag)}</li>`).join("")}</ul>` : ""}
          ${warnings.length ? `<p class="seo-readiness-note">Nota editorial: ${escapeHtml(warnings[0])}</p>` : ""}
        </div>
      </section>

      <section class="search-result-card">
        <header><p class="eyebrow">Así puede leerse en buscador</p><span>Vista de resultado</span></header>
        <div class="search-result-url">nexiagp.com${escapeHtml(path)}</div>
        <strong>${escapeHtml(seo.meta_title)}</strong>
        <p>${escapeHtml(seo.meta_description || "Añade una descripción de resultado.")}</p>
      </section>

      <div class="seo-fields-board">
        <article class="seo-field seo-field-wide">
          <span>Título que verá quien busca</span>
          <strong>${escapeHtml(seo.meta_title)}</strong>
          <small>${seo.meta_title.length} caracteres · marca al final</small>
        </article>
        <article class="seo-field seo-field-wide">
          <span>Descripción que acompaña al resultado</span>
          <p>${escapeHtml(seo.meta_description || "Pendiente")}</p>
          <small>${(seo.meta_description || "").length} caracteres · una promesa clara, sin sobrecargarla</small>
        </article>
        <article class="seo-field"><span>Dirección pública</span><strong>/${escapeHtml(seo.slug || "")}</strong><small>URL corta y legible</small></article>
        <article class="seo-field"><span>Dirección canónica</span><strong>${escapeHtml(path)}</strong><small>La referencia que deben indexar los buscadores</small></article>
        <article class="seo-field"><span>Foco de la búsqueda</span><strong>${escapeHtml(blog.brief?.primary_keyword || "Pendiente")}</strong><small>Densidad estimada: ${escapeHtml(density)}</small></article>
        <article class="seo-field"><span>Para compartir</span><strong>${escapeHtml(seo.open_graph?.og_title || seo.meta_title)}</strong><small>${escapeHtml(seo.open_graph?.og_locale || "es_ES")} · ${escapeHtml(seo.open_graph?.og_type || "article")}</small></article>
      </div>

      <section class="schema-card">
        <header>
          <div><p class="eyebrow">Datos estructurados</p><h4>Cómo entiende el artículo un buscador</h4></div>
          <span class="pill">${escapeHtml(schemaType)}</span>
        </header>
        <div class="schema-facts">
          <div><span>Artículo</span><strong>${escapeHtml(schema.headline || blog.title || "Pendiente")}</strong></div>
          <div><span>Autor</span><strong>${escapeHtml(schemaAuthor || "Nexia Growth Partner")}</strong></div>
          <div><span>Editor</span><strong>${escapeHtml(schemaPublisher || "Nexia GP")}</strong></div>
          <div><span>Fecha</span><strong>${escapeHtml(datePublished)}</strong></div>
        </div>
        <details class="schema-code-detail">
          <summary>Ver JSON-LD técnico</summary>
          <pre class="copy-block">${escapeHtml(seo.schema_jsonld || "")}</pre>
        </details>
      </section>
    </div>
  `;
}

function blogBriefPanel(brief) {
  if (!brief || !brief.h1) return `<div class="empty">Este artículo aún no tiene un enfoque editorial generado.</div>`;
  const internalLinks = (brief.internal_links || []).filter((link) => safeInternalHref(link?.url_path));
  const secondary = brief.secondary_keywords || [];
  const lsi = brief.lsi_terms || [];
  return `
    <div class="brief-review-board">
      <section class="brief-thesis-card">
        <p class="eyebrow">La idea que debe defender el artículo</p>
        <h4>${escapeHtml(brief.core_thesis || brief.thought_leadership_angle || "Pendiente")}</h4>
        ${brief.thought_leadership_angle ? `<p>${escapeHtml(brief.thought_leadership_angle)}</p>` : ""}
      </section>

      <div class="brief-facts-grid">
        <article><span>Para quién se escribe</span><strong>${escapeHtml(brief.target_persona || "Pendiente")}</strong></article>
        <article><span>Qué busca esa persona</span><strong>${escapeHtml(friendlyBriefValue("intent", brief.search_intent))}</strong></article>
        <article><span>Momento del recorrido</span><strong>${escapeHtml(friendlyBriefValue("funnel", brief.funnel_stage))}</strong></article>
        <article><span>Keyword principal</span><strong>${escapeHtml(brief.primary_keyword || "Pendiente")}</strong></article>
      </div>

      <section class="keyword-plan-card">
        <header><p class="eyebrow">Cobertura de búsqueda</p><h4>Palabras y contexto que el texto debe cubrir</h4></header>
        <div class="keyword-plan-grid">
          <div><span>Keywords de apoyo</span><p>${secondary.length ? secondary.map((term) => `<i>${escapeHtml(term)}</i>`).join("") : "Pendiente"}</p></div>
          <div><span>Vocabulario de contexto</span><p>${lsi.length ? lsi.map((term) => `<i>${escapeHtml(term)}</i>`).join("") : "Pendiente"}</p></div>
        </div>
      </section>

      ${brief.lead_magnet_suggestion?.title ? `<section class="lead-magnet-card"><span>${iconSvg("spark")}</span><div><p class="eyebrow">Recurso de valor</p><strong>${escapeHtml(brief.lead_magnet_suggestion.title)}</strong><small>Ubicación sugerida: sección ${escapeHtml(String(brief.lead_magnet_suggestion.placement_section_index || "final"))}</small></div></section>` : ""}

      <section class="internal-links-board">
        <header><p class="eyebrow">Conexión con la web</p><h4>Enlaces internos propuestos</h4><span>${internalLinks.length} ${internalLinks.length === 1 ? "enlace" : "enlaces"}</span></header>
        ${internalLinks.length ? `<div class="internal-links-grid">${internalLinks.map((link) => `
          <a class="internal-link-card" href="${escapeAttr(link.url_path)}" target="_blank" rel="noopener">
            <small>${escapeHtml(link.url_path)}</small>
            <strong>${escapeHtml(link.anchor)}</strong>
            <p>${escapeHtml(link.rationale || "Abre esta página relacionada.")}</p>
            <em>Ver destino ${iconSvg("chevron")}</em>
          </a>`).join("")}</div>` : `<div class="empty">No hay enlaces internos sugeridos.</div>`}
      </section>

      ${(brief.notes_for_writer || []).length ? `<details class="writer-notes"><summary>Notas y límites para quien revise el texto</summary><ul>${brief.notes_for_writer.map((note) => `<li>${escapeHtml(note)}</li>`).join("")}</ul></details>` : ""}
    </div>
  `;
}

function blogFiguresPanel(blogId, figures) {
  if (!figures.length) return `<div class="empty">Este blog no requiere imágenes.</div>`;
  return `
    <section class="figures-review-board">
      <header class="figures-review-head">
        <div><p class="eyebrow">Piezas visuales del artículo</p><h4>Comprueba qué imagen acompaña cada momento de lectura</h4></div>
        <span>${figures.length} ${figures.length === 1 ? "imagen" : "imágenes"}</span>
      </header>
      <div class="figures-grid">${figures.map((f) => figureCard(blogId, f)).join("")}</div>
    </section>`;
}

function figureCard(blogId, figure) {
  const id = escapeAttr(figure.figure_id);
  const hasImage = !!figure.image;
  const displayUrl = hasImage ? (figure.image.displayUrl || figure.image.brandedUrl || figure.image.url) : "";
  const blogCfg = (app.state.settings && app.state.settings.blog) || {};
  // Map settings.blog.imageQuality -> select value (the backend remaps low|standard|high -> low|medium|high).
  const cfgQualityToSelect = { low: "low", standard: "medium", high: "high" };
  const defaultQuality = cfgQualityToSelect[blogCfg.imageQuality || "standard"] || "medium";
  const figureTitle = figure.caption || `Imagen para la sección ${figure.section_index}`;
  return `
    <article class="figure-card">
      <header>
        <div><p class="eyebrow">Imagen ${escapeHtml(figure.figure_id)}</p><strong>Sección ${escapeHtml(String(figure.section_index))}</strong></div>
        ${hasImage ? badge(brandTreatmentLabel(figure.image), "published") : badge("Pendiente", "draft")}
      </header>
      ${hasImage ? `<button class="figure-thumb-button" type="button" data-action="blog-figure-preview" data-blog="${escapeAttr(blogId)}" data-fig="${id}" aria-label="Ampliar ${escapeAttr(figureTitle)}"><img class="figure-thumb" src="${escapeAttr(displayUrl)}" alt="${escapeAttr(figureTitle)}" loading="lazy" /><span>${iconSvg("expand")}Ampliar</span></button>` : `<div class="figure-placeholder">Aún no se ha generado esta imagen</div>`}
      <div class="figure-copy"><strong>${escapeHtml(figureTitle)}</strong>${figure.image_prompt ? `<p>${escapeHtml(figure.image_prompt)}</p>` : ""}${hasImage && figure.image.estimatedCostCents != null ? `<small>Coste estimado: ${escapeHtml(String(Number(figure.image.estimatedCostCents).toFixed(1)))} c</small>` : ""}</div>
      ${hasImage ? `<div class="figure-card-actions"><button class="ghost-button small image-download-button" type="button" data-action="image-download" data-url="${escapeAttr(displayUrl)}" data-filename="${escapeAttr(imageDownloadFilename(`blog-${blogId}-${figure.figure_id}`))}">${iconSvg("download")}Descargar PNG</button></div>` : ""}
      <details class="figure-production-details">
        <summary>${iconSvg("spark")}${hasImage ? "Crear una alternativa visual" : "Generar esta imagen"}</summary>
        <div class="figure-controls" id="figopts-${escapeAttr(blogId)}-${id}">
          <div class="two-cols">
            <label>Formato
              <select class="fig-size">
                ${visualSelectOptions("formats", figure.image?.config?.size || "2048x1152")}
              </select>
            </label>
            <label>Calidad
              <select class="fig-quality">
                <option value="low" ${defaultQuality === "low" ? "selected" : ""}>Ligera (borrador)</option>
                <option value="medium" ${defaultQuality === "medium" ? "selected" : ""}>Estándar</option>
                <option value="high" ${defaultQuality === "high" ? "selected" : ""}>Alta</option>
              </select>
            </label>
          </div>
          <div class="two-cols">
            <label>Qué debe comunicar
              <select class="fig-direction">
                ${visualSelectOptions("directions", figure.image?.config?.direction || "territorio_infraestructura")}
              </select>
            </label>
            <label>Encuadre
              <select class="fig-composition">
                ${visualSelectOptions("compositions", figure.image?.config?.composition || "contexto_amplio")}
              </select>
            </label>
          </div>
          ${brandTreatmentControls({
            frameClass: "fig-frame",
            logoClass: "fig-logo",
            withFrame: figure.image?.config?.withFrame ?? false,
            withLogo: figure.image?.config?.withLogo ?? (figure.image?.config?.withFrame ?? false),
            note: "Opcional en blog; el texto de la imagen no se modifica.",
          })}
          <label>Un matiz opcional<textarea class="fig-notes" rows="2" placeholder="Ej.: luz de primera hora, una escena sin personas..."></textarea></label>
          <button class="primary-button" type="button" data-action="blog-figure-generate" data-blog="${escapeAttr(blogId)}" data-fig="${id}">${iconSvg("spark")}${hasImage ? "Crear propuesta visual" : "Generar imagen"}</button>
        </div>
      </details>
    </article>
  `;
}

function renderLibrary() {
  const files = getFilteredFiles();
  const pending = (app.state.files || []).filter((file) => !["completed", "local_only"].includes(file.status)).length;
  document.getElementById("libraryView").innerHTML = `
    ${manufacturerSourcesPanel()}
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
        <p class="form-hint muted">Cada fuente muestra su estado de sincronización y fecha de actualización. La sincronización se ejecuta bajo demanda para no consumir API sin confirmación del equipo.</p>
      </form>
      <div class="panel">
        <div class="library-list-head">
          <div><h3>Fuentes cargadas</h3><p class="muted">${app.state.files.length} registradas${pending ? ` · ${pending} requieren atención` : " · todas al día"}</p></div>
          ${pending ? `<span class="pill is-warn">${pending} por revisar</span>` : badge("Saludable", "published")}
        </div>
        ${filesToolbar()}
        <div id="filesList">${files.length ? `<div class="file-list">${files.map(fileRow).join("")}</div>` : `<div class="empty">Ninguna fuente coincide con el filtro.</div>`}</div>
      </div>
    </div>
  `;
}

function manufacturerSourcesPanel() {
  const sources = app.state.manufacturerSources || [];
  const updated = sources.filter((source) => source.website?.lastStatus === "updated").length;
  const xEnabled = sources.filter((source) => source.social?.x?.enabled).length;
  return `
    <section class="manufacturer-sources-panel" aria-labelledby="manufacturer-sources-title">
      <header class="manufacturer-sources-head">
        <div>
          <p class="eyebrow">Fuentes de fabricantes</p>
          <h3 id="manufacturer-sources-title">${sources.length} marcas verificadas desde nexiagp.com</h3>
          <p>Actualiza solo la web oficial de la marca que necesites. El resultado queda en la biblioteca como fuente local y no condiciona la IA hasta sincronizarlo expresamente.</p>
        </div>
        <div class="manufacturer-source-summary">
          <span>${updated} web${updated === 1 ? " actualizada" : "s actualizadas"}</span>
          <span>${xEnabled} cuenta${xEnabled === 1 ? " X preparada" : "s X preparadas"}</span>
        </div>
      </header>
      <div class="manufacturer-sources-notice">
        <strong>Redes sociales:</strong> se detectan enlaces desde cada web. X solo se consulta mediante su API oficial, con una cuenta confirmada y el token privado <code>X_API_BEARER_TOKEN</code>; al activarla se revisa en el cron diario. Instagram y LinkedIn quedan visibles para revisión manual.
      </div>
      <div class="manufacturer-source-grid">
        ${sources.map(manufacturerSourceCard).join("")}
      </div>
    </section>`;
}

function manufacturerSourceCard(source) {
  const web = source.website || {};
  const x = source.social?.x || {};
  const socials = source.discoveredSocials || [];
  const websiteStatus = web.lastStatus === "updated" ? `Actualizada ${formatTimestamp(web.lastSyncAt)}`
    : web.lastStatus === "error" ? (web.lastError || "No se pudo actualizar")
      : "Aún no actualizada";
  const xStatus = !x.enabled ? "Desactivado"
    : !x.credentialsConfigured ? "Falta token privado"
      : !x.handle ? "Confirma el usuario"
        : x.status === "updated" ? `Consultada ${formatTimestamp(x.lastSyncAt)}`
          : (x.lastError || "Pendiente de consulta");
  const discovered = socials.length
    ? socials.map((social) => `<a href="${escapeAttr(social.url)}" target="_blank" rel="noopener">${escapeHtml(social.network === "x" ? "X" : social.network)}</a>`).join(" · ")
    : "Se detectarán al actualizar la web";
  return `
    <form class="manufacturer-source-form" data-id="${escapeAttr(source.id)}">
      <header class="manufacturer-source-card-head">
        <div><p class="eyebrow">${escapeHtml(source.sector || "Fabricante")}</p><h4>${escapeHtml(source.name)}</h4></div>
        <span class="status-badge ${web.enabled ? "published" : "draft"}">${web.enabled ? "Web activa" : "Web pausada"}</span>
      </header>
      <a class="manufacturer-site-link" href="${escapeAttr(web.url || "#")}" target="_blank" rel="noopener">Web oficial ↗</a>
      <div class="manufacturer-source-status">
        <span><strong>Web</strong>${escapeHtml(websiteStatus)}${web.pages ? ` · ${escapeHtml(String(web.pages))} páginas` : ""}</span>
        <span><strong>X</strong>${escapeHtml(xStatus)}</span>
      </div>
      <p class="manufacturer-discovered"><strong>Redes detectadas:</strong> ${discovered}${x.candidateHandle && !x.handle ? ` · posible @${escapeHtml(x.candidateHandle)}` : ""}</p>
      <div class="manufacturer-card-actions">
        <button class="secondary-button small" type="button" data-action="manufacturer-web-sync" data-id="${escapeAttr(source.id)}">Actualizar web</button>
        <button class="ghost-button small" type="button" data-action="manufacturer-website-toggle" data-id="${escapeAttr(source.id)}" data-enabled="${web.enabled ? "true" : "false"}">${web.enabled ? "Pausar" : "Activar"}</button>
      </div>
      <div class="manufacturer-x-config">
        <label>Usuario oficial de X
          <input name="xHandle" value="${escapeAttr(x.handle || "")}" placeholder="ej. marca_oficial" autocomplete="off" />
        </label>
        <label class="switch-row"><span>Monitorizar X</span><input name="xEnabled" type="checkbox" ${x.enabled ? "checked" : ""} /></label>
        <div class="manufacturer-card-actions">
          <button class="ghost-button small" type="submit">Guardar X</button>
          <button class="ghost-button small" type="button" data-action="manufacturer-x-sync" data-id="${escapeAttr(source.id)}" ${x.enabled && x.handle && x.credentialsConfigured ? "" : "disabled"}>Consultar X</button>
        </div>
      </div>
    </form>`;
}

function getFilteredFiles() {
  const files = app.state.files || [];
  const f = app.fileFilters || (app.fileFilters = { status: "all", q: "" });
  const q = (f.q || "").trim().toLowerCase();
  return files.filter((file) => {
    const normalized = file.status === "completed" ? "healthy" : file.status === "local_only" ? "local" : "attention";
    if (f.status !== "all" && normalized !== f.status) return false;
    return !q || [file.name, file.category, file.source, file.status].filter(Boolean).join(" ").toLowerCase().includes(q);
  });
}

function filesToolbar() {
  const f = app.fileFilters || { status: "all", q: "" };
  const chip = (id, label) => `<button class="filter-chip ${f.status === id ? "is-active" : ""}" type="button" data-action="files-filter" data-status="${id}">${label}</button>`;
  return `<div class="list-toolbar compact library-toolbar">
    <div class="filter-chips">${chip("all", "Todas")}${chip("healthy", "Sincronizadas")}${chip("attention", "Por revisar")}${chip("local", "Locales")}</div>
    <input id="filesSearch" class="list-search" type="search" placeholder="Buscar fuente, categoría o estado…" value="${escapeAttr(f.q || "")}" />
  </div>`;
}

function renderLibraryList() {
  const list = document.getElementById("filesList");
  if (!list) return;
  const files = getFilteredFiles();
  list.innerHTML = files.length ? `<div class="file-list">${files.map(fileRow).join("")}</div>` : `<div class="empty">Ninguna fuente coincide con el filtro.</div>`;
  document.querySelectorAll("[data-action='files-filter']").forEach((button) => button.classList.toggle("is-active", button.dataset.status === app.fileFilters.status));
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
          ${promptPath("Adaptación Instagram", "src/ai/prompts/transformers/adaptacion_instagram_v1.txt")}
        </div>
      </div>
      <div class="panel">
        <h3>7 prompts maestros</h3>
        <div class="prompt-list">${promptRows}</div>
      </div>
    </div>
  `;
}

function renderCalendar() {
  const posts = allEditorialPosts();
  const blogs = app.state.blogs || [];
  const postBacklog = posts.filter((post) => !post.scheduledFor && post.status !== "published");
  const blogBacklog = blogs.filter((blog) => !blog.scheduledFor && blog.status !== "published");
  const timeline = calendarTimelineEntries(posts, blogs);
  const activeType = app.calendarType === "blogs"
    ? (blogBacklog.length || !postBacklog.length ? "blogs" : "posts")
    : (postBacklog.length || !blogBacklog.length ? "posts" : "blogs");
  app.calendarType = activeType;
  const candidates = activeType === "blogs" ? blogBacklog : postBacklog;
  const selected = calendarSelectedItem();
  document.getElementById("calendarView").innerHTML = `
    <div class="calendar-intro panel">
      <div><p class="eyebrow">Mesa de programación</p><h3>Elige la pieza correcta antes de reservarle un hueco</h3></div>
      <p>Planificar cambia la pieza a <strong>Programada</strong>. No publica por sí sola: la integración social sigue siendo un paso independiente.</p>
    </div>
    <div class="calendar-workbench">
      <section class="panel calendar-picker">
        <header class="calendar-section-head"><div><p class="eyebrow">1 · Seleccionar pieza</p><h3>Por planificar</h3><p class="muted">${postBacklog.length + blogBacklog.length} piezas disponibles</p></div>${badge("Revisión manual", "draft")}</header>
        <div class="calendar-type-tabs" role="tablist" aria-label="Tipo de pieza a planificar">
          <button class="calendar-type-tab ${activeType === "posts" ? "is-active" : ""}" type="button" role="tab" aria-selected="${activeType === "posts"}" data-action="calendar-type-select" data-kind="posts">${iconSvg("image")}Posts <span>${postBacklog.length}</span></button>
          <button class="calendar-type-tab ${activeType === "blogs" ? "is-active" : ""}" type="button" role="tab" aria-selected="${activeType === "blogs"}" data-action="calendar-type-select" data-kind="blogs">${iconSvg("article")}Blogs <span>${blogBacklog.length}</span></button>
        </div>
        <div class="calendar-candidate-list">
          ${candidates.length ? candidates.map((item) => activeType === "posts" ? calendarPostCandidate(item, selected) : calendarBlogCandidate(item, selected)).join("") : `<div class="empty">No hay ${activeType === "posts" ? "posts" : "blogs"} pendientes de planificación.</div>`}
        </div>
      </section>
      <section class="panel calendar-programming">
        ${selected ? calendarProgrammingPanel(selected) : calendarProgrammingEmpty(activeType)}
      </section>
    </div>
    ${calendarAgendaSection(timeline)}`;
}

function calendarTimelineEntries(posts, blogs) {
  const makeEntries = (items, kind) => items.map((item) => {
    const date = item.scheduledFor || (item.status === "published" ? item.publishedAt : "");
    return { kind, item, date, state: item.status === "published" ? "published" : "scheduled" };
  }).filter((entry) => entry.date && !Number.isNaN(new Date(entry.date).getTime()));
  return [...makeEntries(posts, "post"), ...makeEntries(blogs, "blog")]
    .sort((a, b) => String(a.date).localeCompare(String(b.date)));
}

function calendarAgendaSection(timeline) {
  const view = app.calendarAgendaView === "list" ? "list" : "month";
  const planned = timeline.filter((entry) => entry.state === "scheduled").length;
  const published = timeline.filter((entry) => entry.state === "published").length;
  return `<section class="panel calendar-upcoming"><header class="calendar-section-head"><div><p class="eyebrow">Agenda editorial</p><h3>Ocupación del calendario</h3><p class="muted">${planned} programadas${published ? ` · ${published} publicadas` : ""}</p></div><div class="calendar-agenda-switch" role="tablist" aria-label="Vista de agenda"><button class="${view === "month" ? "is-active" : ""}" type="button" role="tab" aria-selected="${view === "month"}" data-action="calendar-agenda-view" data-view="month">${iconSvg("calendar")}Mes</button><button class="${view === "list" ? "is-active" : ""}" type="button" role="tab" aria-selected="${view === "list"}" data-action="calendar-agenda-view" data-view="list">${iconSvg("layout")}Agenda</button></div></header>
    ${view === "month" ? calendarMonthBoard(timeline) : `<div class="calendar-list">${timeline.length ? timeline.map(calendarScheduledCard).join("") : `<div class="empty">Aún no hay piezas programadas.</div>`}</div>`}
  </section>`;
}

function calendarMonthBoard(timeline) {
  const month = calendarResolvedMonth(timeline);
  const year = Number(month.slice(0, 4));
  const monthIndex = Number(month.slice(5, 7)) - 1;
  const firstWeekday = (new Date(year, monthIndex, 1).getDay() + 6) % 7;
  const daysInMonth = new Date(year, monthIndex + 1, 0).getDate();
  const eventsByDay = new Map();
  timeline.forEach((entry) => {
    const key = calendarDateKey(entry.date);
    if (!eventsByDay.has(key)) eventsByDay.set(key, []);
    eventsByDay.get(key).push(entry);
  });
  const firstScheduledDay = [...eventsByDay.keys()].find((key) => key.startsWith(month));
  const selectedDay = app.calendarSelectedDay?.startsWith(month) ? app.calendarSelectedDay : (firstScheduledDay || null);
  app.calendarSelectedDay = selectedDay;
  const cells = [];
  for (let index = 0; index < firstWeekday; index += 1) cells.push(`<span class="calendar-month-filler" aria-hidden="true"></span>`);
  for (let day = 1; day <= daysInMonth; day += 1) {
    const key = `${month}-${String(day).padStart(2, "0")}`;
    const entries = eventsByDay.get(key) || [];
    const isSelected = key === selectedDay;
    const hasPublished = entries.some((entry) => entry.state === "published");
    const hasScheduled = entries.some((entry) => entry.state === "scheduled");
    cells.push(`<button class="calendar-month-day ${entries.length ? "has-content" : "is-free"} ${hasScheduled ? "has-scheduled" : ""} ${hasPublished ? "has-published" : ""} ${isSelected ? "is-selected" : ""}" type="button" data-action="calendar-day-select" data-date="${key}" aria-pressed="${isSelected}"><span class="calendar-day-number">${day}</span><span class="calendar-day-state">${entries.length ? `${entries.length} ${entries.length === 1 ? "pieza" : "piezas"}` : "Libre"}</span>${entries.length ? `<span class="calendar-day-marks">${entries.slice(0, 3).map((entry) => `<i class="${entry.state}" title="${escapeAttr(entry.state === "published" ? "Publicada" : "Programada")}"></i>`).join("")}</span>` : ""}</button>`);
  }
  const dayEntries = selectedDay ? (eventsByDay.get(selectedDay) || []) : [];
  return `<div class="calendar-month-shell"><div class="calendar-month-head"><button class="icon-button" type="button" data-action="calendar-month-change" data-direction="previous" aria-label="Mes anterior">${iconSvg("chevron")}</button><div><strong>${escapeHtml(calendarMonthLabel(year, monthIndex))}</strong><small>Haz clic en un día para revisar su contenido</small></div><button class="icon-button calendar-next-month" type="button" data-action="calendar-month-change" data-direction="next" aria-label="Mes siguiente">${iconSvg("chevron")}</button></div><div class="calendar-weekdays" aria-hidden="true">${["L", "M", "X", "J", "V", "S", "D"].map((day) => `<span>${day}</span>`).join("")}</div><div class="calendar-month-grid">${cells.join("")}</div>${calendarDayDetail(selectedDay, dayEntries)}</div>`;
}

function calendarResolvedMonth(timeline) {
  if (/^\d{4}-\d{2}$/.test(app.calendarMonth || "")) return app.calendarMonth;
  const firstPlanned = timeline.find((entry) => entry.state === "scheduled") || timeline[0];
  const source = firstPlanned ? new Date(firstPlanned.date) : new Date();
  app.calendarMonth = `${source.getFullYear()}-${String(source.getMonth() + 1).padStart(2, "0")}`;
  return app.calendarMonth;
}

function calendarShiftMonth(amount) {
  const [year, month] = calendarResolvedMonth([]).split("-").map(Number);
  const next = new Date(year, month - 1 + amount, 1);
  return `${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, "0")}`;
}

function calendarDateKey(value) {
  const date = new Date(value);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function calendarMonthLabel(year, monthIndex) {
  return new Intl.DateTimeFormat("es-ES", { month: "long", year: "numeric" }).format(new Date(year, monthIndex, 1));
}

function calendarDayDetail(dateKey, entries) {
  const label = dateKey ? new Intl.DateTimeFormat("es-ES", { weekday: "long", day: "numeric", month: "long" }).format(new Date(`${dateKey}T12:00:00`)) : "Día seleccionado";
  return `<section class="calendar-day-detail"><header><div><p class="eyebrow">Detalle del día</p><h4>${escapeHtml(label)}</h4></div><span>${entries.length ? `${entries.length} ${entries.length === 1 ? "pieza" : "piezas"}` : "Hueco disponible"}</span></header>${entries.length ? `<div class="calendar-day-events">${entries.map((entry) => calendarDayEvent(entry)).join("")}</div>` : `<p class="calendar-day-empty">No hay contenido asignado a esta fecha. Puedes reservarla desde la selección de arriba.</p>`}</section>`;
}

function calendarDayEvent(entry) {
  const isBlog = entry.kind === "blog";
  const time = new Intl.DateTimeFormat("es-ES", { hour: "2-digit", minute: "2-digit" }).format(new Date(entry.date));
  return `<article class="calendar-day-event"><span class="calendar-day-event-icon ${entry.state}">${iconSvg(isBlog ? "article" : "image")}</span><div><div class="calendar-candidate-meta">${badge(entry.state === "published" ? "Publicado" : "Programado", entry.state)}<span class="pill">${isBlog ? "Blog" : "Post"}</span><span>${escapeHtml(time)}</span></div><strong>${escapeHtml(calendarTitle(entry.item, entry.kind))}</strong></div></article>`;
}

function calendarSelectedItem() {
  const selection = app.calendarSelection;
  if (!selection?.id) return null;
  const item = selection.kind === "blog"
    ? (app.state.blogs || []).find((blog) => blog.id === selection.id)
    : findPost(selection.id);
  return item ? { kind: selection.kind, item } : null;
}

function calendarTitle(item, kind) {
  if (kind === "blog") return item.title || item.article?.h1 || item.brief?.h1 || item.request?.topic || "Blog editorial";
  return item.title || item.brief?.core_angle || "Post editorial";
}

function calendarExcerpt(item, kind, limit = 210) {
  const text = kind === "blog"
    ? item.brief?.intro_hook || item.brief?.core_thesis || item.request?.topic || "Artículo editorial listo para revisión."
    : item.generation?.copy?.final_post || item.copy || item.idea || "Post editorial listo para revisión.";
  const normalized = String(text).replace(/\s+/g, " ").trim();
  return `${normalized.slice(0, limit)}${normalized.length > limit ? "…" : ""}`;
}

function isCalendarSelected(kind, id) {
  return app.calendarSelection?.kind === kind && app.calendarSelection?.id === id;
}

function calendarPostCandidate(post) {
  const selected = isCalendarSelected("post", post.id);
  const imageUrl = post.image?.displayUrl || post.image?.brandedUrl || post.image?.url || "";
  return `<button class="calendar-post-candidate ${selected ? "is-selected" : ""}" type="button" data-action="calendar-item-select" data-kind="post" data-id="${escapeAttr(post.id)}" aria-pressed="${selected}">
    <span class="calendar-post-thumb ${imageUrl ? "has-image" : ""}">${imageUrl ? `<img src="${escapeAttr(imageUrl)}" alt="" loading="lazy" />` : iconSvg("image")}</span>
    <span class="calendar-candidate-copy">
      <span class="calendar-candidate-meta">${badge(statusLabels[post.status] || "Borrador", post.status || "draft")}<span class="pill">${escapeHtml(labelFor("postTypes", post.brief?.post_type) || "Post")}</span></span>
      <strong>${escapeHtml(calendarTitle(post, "post"))}</strong>
      <small>${escapeHtml(calendarExcerpt(post, "post", 155))}</small>
      <span class="calendar-candidate-action">${selected ? "Seleccionado" : "Seleccionar"}${iconSvg("chevron")}</span>
    </span>
  </button>`;
}

function calendarBlogCandidate(blog) {
  const selected = isCalendarSelected("blog", blog.id);
  const wordCount = blog.wordCount || blog.article?.word_count || 0;
  return `<button class="calendar-blog-candidate calendar-card ${selected ? "is-selected" : ""}" type="button" data-action="calendar-item-select" data-kind="blog" data-id="${escapeAttr(blog.id)}" aria-pressed="${selected}">
    <span class="calendar-blog-marker">${iconSvg("article")}</span>
    <span class="calendar-candidate-copy">
      <span class="calendar-candidate-meta">${badge(statusLabels[blog.status] || "Borrador", blog.status || "draft")}<span class="pill">Blog</span><span>${wordCount ? `${wordCount} palabras` : "Longitud pendiente"}</span></span>
      <strong>${escapeHtml(calendarTitle(blog, "blog"))}</strong>
      <small>${escapeHtml(calendarExcerpt(blog, "blog", 175))}</small>
      <span class="calendar-candidate-action">${selected ? "Seleccionado" : "Seleccionar"}${iconSvg("chevron")}</span>
    </span>
  </button>`;
}

function calendarProgrammingEmpty(activeType) {
  return `<div class="calendar-programming-empty"><span>${iconSvg(activeType === "posts" ? "image" : "article")}</span><div><p class="eyebrow">2 · Reservar hueco</p><h3>Selecciona ${activeType === "posts" ? "un post" : "un blog"}</h3><p>Verás su referencia editorial antes de elegir día y hora.</p></div></div>`;
}

function calendarProgrammingPanel(selection) {
  const { kind, item } = selection;
  const isBlog = kind === "blog";
  const imageUrl = item.image?.displayUrl || item.image?.brandedUrl || item.image?.url || "";
  const wordCount = item.wordCount || item.article?.word_count || 0;
  const context = isBlog
    ? `${wordCount ? `${wordCount} palabras · ` : ""}${item.brief?.search_intent || item.request?.search_intent_hint || "Artículo editorial"}`
    : `${labelFor("postTypes", item.brief?.post_type) || "Post"} · ${item.platform || item.generation?.meta?.channel || "linkedin"}`;
  return `<header class="calendar-section-head"><div><p class="eyebrow">2 · Reservar hueco</p><h3>Añadir al calendario</h3><p class="muted">Confirma la pieza antes de elegir día y hora.</p></div><button class="ghost-button small" type="button" data-action="calendar-selection-clear">Cambiar pieza</button></header>
    <article class="calendar-selection-preview ${isBlog ? "is-blog" : "is-post"}">
      ${isBlog ? `<span class="calendar-selection-blog-mark">${iconSvg("article")}</span>` : `<span class="calendar-selection-image ${imageUrl ? "has-image" : ""}">${imageUrl ? `<img src="${escapeAttr(imageUrl)}" alt="" />` : iconSvg("image")}</span>`}
      <div><div class="calendar-candidate-meta">${badge(statusLabels[item.status] || "Borrador", item.status || "draft")}<span class="pill">${isBlog ? "Blog" : "Post"}</span></div><h4>${escapeHtml(calendarTitle(item, kind))}</h4><p>${escapeHtml(calendarExcerpt(item, kind, isBlog ? 330 : 280))}</p><small>${escapeHtml(context)}</small></div>
    </article>
    <div class="calendar-schedule-form"><label>Día y hora<input class="calendar-date" type="datetime-local" value="${escapeAttr(toDateTimeLocal(item.scheduledFor || ""))}" aria-label="Día y hora para añadir al calendario" /></label><button class="primary-button" type="button" data-action="calendar-schedule" data-kind="${kind}" data-id="${escapeAttr(item.id)}">${iconSvg("calendar")}Añadir ${isBlog ? "blog" : "post"} al calendario</button></div>`;
}

function calendarScheduledCard(entry) {
  const { kind, item, state, date } = entry;
  const isBlog = kind === "blog";
  const scheduledFor = date || "";
  const isPublished = state === "published";
  return `<article class="calendar-card">
    <div class="calendar-card-head"><div>${badge(isPublished ? "Publicado" : statusLabels[item.status] || "Programado", isPublished ? "published" : item.status || "scheduled")}<span class="pill">${isBlog ? "Blog" : escapeHtml(labelFor("postTypes", item.brief?.post_type) || "Post")}</span></div><small>${scheduledFor ? escapeHtml(formatDate(scheduledFor)) : "Sin fecha"}</small></div>
    <h4>${escapeHtml(calendarTitle(item, kind))}</h4>
    <p>${escapeHtml(calendarExcerpt(item, kind, 180))}</p>
    ${isPublished ? "" : `<div class="calendar-card-actions">
      <input class="calendar-date" type="datetime-local" value="${escapeAttr(toDateTimeLocal(scheduledFor))}" aria-label="Fecha y hora de planificación" />
      <button class="secondary-button" type="button" data-action="calendar-reschedule" data-kind="${kind}" data-id="${escapeAttr(item.id)}">${iconSvg("calendar")}Reprogramar</button>
    </div>`}
  </article>`;
}

async function scheduleCalendarItem(kind, id, selectedDate, button) {
  const scheduledAt = new Date(selectedDate);
  if (Number.isNaN(scheduledAt.getTime())) throw new Error("El día y la hora no son válidos.");
  const isBlog = kind === "blog";
  const item = isBlog ? (app.state.blogs || []).find((blog) => blog.id === id) : findPost(id);
  if (!item) throw new Error("La pieza ya no está disponible para planificación.");
  if (!isBlog && item.status !== "ready" && item.status !== "scheduled") {
    throw new Error("Aprueba el post antes de asignarle fecha.");
  }
  const payload = { scheduledFor: scheduledAt.toISOString() };
  if (qualityReviewRequired(item)) {
    if (!confirm(qualityReviewMessage(item?.qualityGate, isBlog ? "blog" : "post"))) return null;
    payload.reviewAcknowledged = true;
  }
  await withLoading(button, () => api(isBlog ? `/api/blogs/${id}` : `/api/posts/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  }));
  return isBlog ? "Blog" : "Post";
}

function toDateTimeLocal(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const offset = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

function renderAutomation() {
  const settings = app.state.settings;
  document.getElementById("automationView").innerHTML = `
    <div class="settings-grid">
      <form class="panel form-grid" id="automationForm">
        <label class="switch-row"><span>Generación automática <span class="field-hint">${settings.schedulerEnabled ? "Activa" : "Pausada"}</span></span><input name="schedulerEnabled" type="checkbox" ${settings.schedulerEnabled ? "checked" : ""} /></label>
        <label>Cadencia en días<input name="cadenceDays" type="number" min="1" max="30" value="${escapeAttr(settings.cadenceDays || 3)}" /></label>
        ${selectField("defaultPostTypeId", "Tipo por defecto", editorialPostTypeOptions(), settings.defaultPostTypeId || "educativo_autoridad")}
        <label>Modo de salida<select name="publishMode">${publishModeOptions(settings.publishMode)}</select></label>
        ${schedulerRotationHint(settings)}
        <p class="form-hint muted">La generación acaba en revisión. Cada post necesita aprobación y fecha; la conexión de redes se verifica por separado.</p>
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

function schedulerRotationHint(settings) {
  const next = settings.schedulerNextThemeTitle || "la primera temática activa";
  return `<p class="automation-rotation-note"><strong>Rotación editorial:</strong> se crea una sola pieza cada ${escapeHtml(String(settings.cadenceDays || 3))} días y se alternan todas las temáticas activas. Siguiente: <strong>${escapeHtml(next)}</strong>. Pausar el interruptor detiene solo las ejecuciones automáticas; “Ejecutar ahora” sigue siendo manual.</p>`;
}

function publishModeOptions(selected) {
  const active = selected === "auto" ? "ready" : selected;
  return `
    <option value="draft" ${active === "draft" ? "selected" : ""}>Borrador</option>
    <option value="ready" ${active === "ready" ? "selected" : ""}>Listo</option>
    <option value="auto" disabled>Automático · pendiente de conexión</option>`;
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
        <label>Modo de salida<select name="publishMode">${publishModeOptions(settings.publishMode)}</select></label>
        <label class="switch-row"><span>Generación automática <span class="field-hint">${settings.schedulerEnabled ? "Activa" : "Pausada"}</span></span><input name="schedulerEnabled" type="checkbox" ${settings.schedulerEnabled ? "checked" : ""} /></label>
        ${schedulerRotationHint(settings)}
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
        <p class="muted">Los 11 tipos disponibles se gestionan desde la pestaña <a href="#strategy" data-nav="strategy">Temáticas</a>. Cada uno tiene su prompt maestro editable en Prompts.</p>
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
              ${["pas", "aida", "thought_leadership", "case_study"].map((v) => `<option value="${v}" ${blog.defaultFramework === v ? "selected" : ""}>${escapeHtml(v.replaceAll("_", " ").toUpperCase())}</option>`).join("")}
            </select>
          </label>
        </div>
        <label>Audiencia por defecto<input name="defaultAudience" value="${escapeAttr(blog.defaultAudience || "fabricantes")}" /></label>
        <h3>Imágenes</h3>
        <p class="muted">Las imágenes de blog usan prompts acotados y un guardarraíl de presupuesto por artículo. La estimación es de planificación; la factura del proveedor prevalece.</p>
        <div class="two-cols">
          <label>Imágenes por artículo<input name="imagesPerArticle" type="number" min="0" max="6" value="${escapeAttr(blog.imagesPerArticle ?? 2)}" /></label>
          <label>Calidad de imagen
            <select name="imageQuality">
              ${["low", "standard", "high"].map((v) => `<option value="${v}" ${blog.imageQuality === v ? "selected" : ""}>${escapeHtml(v)}</option>`).join("")}
            </select>
          </label>
        </div>
        <label>Tope de coste de imágenes por artículo (céntimos)<input name="costTargetCents" type="number" min="0" max="1000" value="${escapeAttr(blog.costTargetCents ?? 30)}" /></label>
        <p class="form-hint muted">Guardarraíl activo antes de cada figura: calcula el coste estimado de salida de GPT Image 2. Usa 0 para desactivarlo; el texto y posibles entradas de edición no están incluidos.</p>
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
      <div class="channel-card">
        <div class="channel-card-head"><strong>Instagram</strong><button class="icon-button" type="button" data-action="copy-adaptation" data-channel="instagram" data-id="${escapeAttr(postId)}" title="Copiar Instagram">${iconSvg("copy")}</button></div>
        <p class="copy-block">${escapeHtml(adaptations.instagram?.caption || "Pendiente de generar")}</p>
        <small>La imagen debe seleccionarse y aprobarse antes de publicar.</small>
      </div>
    </div>
  `;
}

function reviewStat(label, value) {
  return `<div class="review-stat"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`;
}

function qualityReviewRequired(content) {
  const gate = content?.qualityGate || {};
  return Boolean((gate.blockers || []).length && !gate.reviewAcknowledgedAt);
}

function qualityGateBadge(gate) {
  const blockers = gate?.blockers || [];
  if (!blockers.length) return gate?.status === "passed" ? badge("QA verificada", "published") : "";
  return badge(gate?.reviewAcknowledgedAt ? "Revisión registrada" : "Revisión requerida", gate?.reviewAcknowledgedAt ? "published" : "failed");
}

function qualityGateNotice(gate) {
  const blockers = gate?.blockers || [];
  if (!blockers.length) return "";
  const heading = gate?.reviewAcknowledgedAt ? "Revisión humana registrada" : "Antes de aprobar el contenido";
  const items = blockers.map((item) => "<li>" + escapeHtml(item) + "</li>").join("");
  return '<div class="flag-list quality-gate"><strong>' + escapeHtml(heading) + "</strong><ul>" + items + "</ul></div>";
}

function qualityReviewMessage(gate, kind, nextStep = "continuar") {
  const blockers = (gate?.blockers || []).map((item) => "• " + item).join("\n");
  return "Este " + kind + " tiene controles pendientes.\n\n" + blockers + "\n\n¿Confirmas que has realizado la revisión humana y quieres registrarla antes de " + nextStep + "?";
}

function isBlogApprovedForWordPress(blog) {
  return ["ready", "scheduled"].includes(blog?.status);
}

function safeInternalHref(value) {
  const path = String(value || "").trim();
  return /^\/(?!\/)(?!.*(?:^|\/)\.\.(?:\/|$))[A-Za-z0-9._~%/?=&-]*$/.test(path);
}

function safeJsonLdForExport(value) {
  if (!value) return "";
  try {
    const parsed = JSON.parse(value);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return "";
    return JSON.stringify(parsed).replaceAll("<", "\\u003c").replaceAll(">", "\\u003e").replaceAll("&", "\\u0026");
  } catch {
    return "";
  }
}

function approvalChecklist(post) {
  const sources = post.retrieval?.sources || [];
  const flags = post.validation?.review_flags || [];
  const requiresHumanReview = qualityReviewRequired(post) || Boolean(post.validation?.human_review_required || flags.length);
  const acknowledged = Boolean(post.qualityGate?.reviewAcknowledgedAt);
  const image = post.image?.validation;
  const checks = [
    { ok: sources.length > 0, label: sources.length ? `${sources.length} fuentes trazadas` : "Sin fuentes trazadas" },
    { ok: !requiresHumanReview, label: acknowledged ? "Revisión humana registrada" : requiresHumanReview ? "Revisión humana pendiente" : "Sin flags de revisión" },
    { ok: !image || image.valid, label: image ? (image.valid ? "Imagen PNG verificada" : "Imagen pendiente de validar") : "Imagen opcional" },
  ];
  const ready = checks.every((check) => check.ok);
  return `
    <section class="approval-checklist ${ready ? "is-ready" : "needs-review"}">
      <div class="section-label compact"><span>${iconSvg("check")}</span><h3>Salida editorial</h3></div>
      <p>${ready ? "Lista para planificar tras una última lectura." : "Antes de calendarizar, revisa los puntos señalados."}</p>
      <ul>${checks.map((check) => `<li class="${check.ok ? "is-ok" : "is-pending"}"><span>${check.ok ? "✓" : "!"}</span>${escapeHtml(check.label)}</li>`).join("")}</ul>
    </section>`;
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
  const statusLabel = file.status === "in_progress" ? "pendiente de sincronizar" : file.status === "local_only" ? "solo local" : file.status;
  return `
    <div class="file-row">
      <div class="file-row-main">
        <div>
          <h3>${escapeHtml(file.name)}</h3>
          <div class="file-meta">
            ${badge(statusLabel, statusClass)}
            <span class="pill">${escapeHtml(file.category)}</span>
            <span class="pill">${formatBytes(file.size)}</span>
            <span class="pill">Actualizada ${escapeHtml(formatShortDate(file.updatedAt || file.createdAt))}</span>
          </div>
        </div>
        <button class="danger-button" type="button" data-action="file-delete" data-id="${escapeAttr(file.id)}">${iconSvg("trash")}Eliminar</button>
      </div>
      ${file.error ? `<p class="copy-block">${escapeHtml(file.error)}</p>` : ""}
    </div>
  `;
}

function formatShortDate(value) {
  if (!value) return "sin fecha";
  try {
    return new Intl.DateTimeFormat("es-ES", { day: "2-digit", month: "short", year: "numeric" }).format(new Date(value));
  } catch (error) {
    return "sin fecha";
  }
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
  return `<div class="metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value ?? "0")}</strong></div>`;
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
  const response = await fetch(url, { credentials: "same-origin", ...options });
  const data = await response.json().catch(() => ({}));
  if (response.status === 401 && app.auth?.required) handleAuthenticationExpired();
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
  if (channel === "instagram") {
    const instagram = post.adaptations.instagram || {};
    return [instagram.caption, instagram.cta, (instagram.hashtags || []).join(" ")].filter(Boolean).join("\n\n");
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

const FALLBACK_VISUAL_OPTIONS = {
  directions: {
    operacion_real: { label: "Operación real" },
    criterio_experto: { label: "Criterio experto" },
    territorio_infraestructura: { label: "Territorio e infraestructura" },
    producto_en_uso: { label: "Producto en uso" },
    relacion_de_canal: { label: "Relación de canal" },
  },
  compositions: {
    contexto_amplio: { label: "Contexto amplio" },
    altura_humana: { label: "A la altura del trabajo" },
    detalle_de_accion: { label: "Detalle de acción" },
    perspectiva_alta: { label: "Perspectiva alta" },
  },
  formats: {
    "1088x1360": { label: "LinkedIn recomendado (4:5)" },
    "1536x1024": { label: "Editorial horizontal (3:2)" },
    "1024x1024": { label: "Cuadrado (1:1)" },
    "1024x1536": { label: "Vertical narrativo (2:3)" },
    "2048x1152": { label: "Cabecera de blog (16:9)" },
  },
};

function visualSelectOptions(group, selected) {
  const options = app.state?.editorialOptions?.visual?.[group] || FALLBACK_VISUAL_OPTIONS[group] || {};
  return Object.entries(options)
    .map(([value, item]) => `<option value="${escapeAttr(value)}" ${value === selected ? "selected" : ""}>${escapeHtml(item.label || value)}</option>`)
    .join("");
}

function retainedImageVariants(post) {
  const variants = Array.isArray(post.imageVariants) ? post.imageVariants.filter(Boolean) : [];
  if (!variants.length && post.image) return [post.image];
  if (post.image && !variants.some((item) => item.id === post.image.id)) return [post.image, ...variants];
  return variants;
}

function visualVariantsPanel(post, activeImage) {
  const variants = retainedImageVariants(post);
  if (!variants.length) return "";
  const postId = escapeAttr(post.id);
  const activeId = activeImage?.id;
  return `
    <div class="visual-variants" aria-label="Conceptos visuales conservados">
      <div class="visual-variants-head"><strong>Conceptos conservados</strong><span>${variants.length}/${5}</span></div>
      <p class="field-hint">Generar una alternativa no borra la anterior. Elige cuál acompaña al copy antes de aprobarla.</p>
      <div class="visual-variants-grid">
        ${variants.map((variant) => {
          const variantId = escapeAttr(variant.id || "");
          const selected = variant.id === activeId;
          const url = variant.displayUrl || variant.brandedUrl || variant.url || "";
          const isApproved = variant.review?.status === "approved";
          return `
            <article class="visual-variant ${selected ? "is-active" : ""}">
              <button class="visual-variant-select" type="button" data-action="image-variant-select" data-id="${postId}" data-image="${variantId}" ${selected ? "aria-current=\"true\"" : ""}>
                <img src="${escapeAttr(url)}" alt="Concepto visual ${selected ? "activo" : "alternativo"}" loading="lazy" />
                <span>${selected ? "Activo" : "Usar este"}</span>
              </button>
              <div class="visual-variant-meta">
                <span>${escapeHtml(variant.config?.direction ? labelForVisual("directions", variant.config.direction) : "Concepto anterior")}</span>
                <div class="visual-variant-actions">
                  ${url ? `<button class="ghost-button small image-download-button" type="button" data-action="image-download" data-url="${escapeAttr(url)}" data-filename="${escapeAttr(imageDownloadFilename(`${post.title || post.brief?.core_angle || "post-nexia"}-${variant.config?.direction || "concepto"}`))}">${iconSvg("download")}PNG</button>` : ""}
                  ${isApproved ? badge("Revisada", "published") : `<button class="ghost-button small" type="button" data-action="image-review" data-id="${postId}" data-image="${variantId}">Aprobar</button>`}
                </div>
              </div>
            </article>`;
        }).join("")}
      </div>
    </div>`;
}

function labelForVisual(group, key) {
  const item = app.state?.editorialOptions?.visual?.[group]?.[key] || FALLBACK_VISUAL_OPTIONS[group]?.[key];
  return item?.label || key || "";
}

function visualChoiceCards(group, selected, field) {
  const options = app.state?.editorialOptions?.visual?.[group] || FALLBACK_VISUAL_OPTIONS[group] || {};
  return `
    <div class="visual-choice-grid" role="group" aria-label="${escapeAttr(field === "direction" ? "Qué debe comunicar la imagen" : "Cómo debe encuadrarse")}">
      ${Object.entries(options).map(([value, item]) => `
        <button class="visual-choice ${value === selected ? "is-selected" : ""}" type="button" data-action="visual-option-select" data-field="${escapeAttr(field)}" data-value="${escapeAttr(value)}" aria-pressed="${value === selected ? "true" : "false"}">
          <strong>${escapeHtml(item.label || value)}</strong>
          <small>${escapeHtml(item.description || "")}</small>
        </button>`).join("")}
    </div>`;
}

function brandTreatmentLabel(image) {
  const withFrame = image?.config?.withFrame ?? image?.cloudinary?.withFrame ?? false;
  const withLogo = image?.config?.withLogo ?? image?.cloudinary?.withLogo ?? withFrame;
  if (withFrame && withLogo) return "Marco + logo Nexia";
  if (withFrame) return "Solo marco";
  if (withLogo) return "Solo logo Nexia";
  return "Imagen limpia";
}

function brandTreatmentControls({ frameClass, logoClass, withFrame, withLogo, note }) {
  return `
    <fieldset class="brand-treatment-controls">
      <legend>Acabado de marca</legend>
      <p class="field-hint">Elige cada elemento por separado. Se compone localmente tras generar la imagen.</p>
      <div class="brand-treatment-options">
        <label class="switch-row"><span>Marco Nexia</span><input type="checkbox" class="${escapeAttr(frameClass)}" ${withFrame ? "checked" : ""} /></label>
        <label class="switch-row"><span>Logo Nexia</span><input type="checkbox" class="${escapeAttr(logoClass)}" ${withLogo ? "checked" : ""} /></label>
      </div>
      ${note ? `<p class="field-hint brand-treatment-note">${escapeHtml(note)}</p>` : ""}
    </fieldset>`;
}

function imageSection(post) {
  const img = post.image;
  const id = escapeAttr(post.id);
  const defaults = post.imageDefaults || { withFrame: true, withLogo: true };
  const withFrame = img?.config?.withFrame ?? img?.cloudinary?.withFrame ?? defaults.withFrame ?? true;
  const withLogo = img?.config?.withLogo ?? img?.cloudinary?.withLogo ?? defaults.withLogo ?? withFrame;
  const validation = img?.validation;
  const approved = img?.review?.status === "approved";
  const existingImage = img ? `
    <div class="generated-image-wrap visual-current-details">
      <div class="image-meta">
        <span class="status-badge ${(withFrame || withLogo) ? "published" : "draft"}">${escapeHtml(brandTreatmentLabel(img))}</span>
        ${approved ? badge("Revisada por editor", "published") : badge("Revisión visual pendiente", "draft")}
        ${validation?.valid ? `<span class="status-badge published">PNG verificado</span><span class="pill">${escapeHtml(`${validation.width}×${validation.height}`)}</span>` : ""}
        <span class="pill">${escapeHtml(labelForVisual("directions", img.config?.direction))}</span>
        <span class="pill">${escapeHtml(labelForVisual("compositions", img.config?.composition))}</span>
      </div>
      ${img.sceneRationale ? `<div class="visual-rationale"><strong>Por qué esta escena</strong><p>${escapeHtml(img.sceneRationale)}</p></div>` : ""}
      <div class="visual-review-checklist">
        <strong>Control antes de usarla</strong>
        <span>Escena creíble · sujeto correcto · sin texto ni mapas · encuadre limpio · logo no invade</span>
      </div>
      <details class="image-prompt-detail">
        <summary>Ver prompt generado</summary>
        <p class="copy-block">${escapeHtml(img.prompt || "")}</p>
      </details>
    </div>
  ` : "";
  return `
    <section class="visual-workbench" aria-label="Gestión de la imagen del post">
      <details class="visual-manager" id="img-manager-${id}" ${img ? "" : "open"}>
        <summary>
          <div>
            <p class="eyebrow">Dirección visual</p>
            <h3>${img ? "Ajustar, comparar o crear una alternativa" : "Define la primera imagen de esta pieza"}</h3>
            <p>${img ? "La imagen activa ya está arriba: aquí puedes entenderla, comparar conceptos o crear una versión nueva." : "Primero decide qué debe demostrar la imagen; después el encuadre y el formato."}</p>
          </div>
          <span class="visual-manager-trigger">${iconSvg("spark")}${img ? "Gestionar" : "Empezar"}</span>
        </summary>
        <div class="visual-manager-body">
          ${existingImage}
          ${visualVariantsPanel(post, img)}
          <div class="image-gen-options" id="img-opts-${id}">
            <div class="visual-option-heading">
              <span>1</span>
              <div><strong>¿Qué debe contar la imagen?</strong><small>Elige una intención; cada opción explica el resultado que se busca.</small></div>
            </div>
            <input class="img-direction" type="hidden" value="${escapeAttr(img?.config?.direction || "operacion_real")}" />
            ${visualChoiceCards("directions", img?.config?.direction || "operacion_real", "direction")}
            <div class="visual-option-heading">
              <span>2</span>
              <div><strong>¿Desde dónde se ve?</strong><small>El encuadre ordena la escena sin cambiar el mensaje.</small></div>
            </div>
            <input class="img-composition" type="hidden" value="${escapeAttr(img?.config?.composition || "contexto_amplio")}" />
            ${visualChoiceCards("compositions", img?.config?.composition || "contexto_amplio", "composition")}
            <div class="visual-option-heading compact-step">
              <span>3</span>
              <div><strong>Formato y acabado</strong><small>Elige el soporte final de esta variante.</small></div>
            </div>
            <div class="two-cols visual-technical-fields">
              <label>Formato
                <select class="img-size">
                  ${visualSelectOptions("formats", img?.config?.size || "1088x1360")}
                </select>
              </label>
              <label>Calidad
                <select class="img-quality">
                  <option value="medium" ${(img?.config?.quality || "medium") === "medium" ? "selected" : ""}>Media · recomendada</option>
                  <option value="high" ${img?.config?.quality === "high" ? "selected" : ""}>Alta · versión final</option>
                  <option value="low" ${img?.config?.quality === "low" ? "selected" : ""}>Borrador rápido</option>
                </select>
              </label>
            </div>
            ${brandTreatmentControls({
              frameClass: "img-frame",
              logoClass: "img-logo",
              withFrame,
              withLogo,
              note: "Puedes combinar ambos, o dejar la pieza limpia.",
            })}
            <label>Un matiz opcional <span class="field-hint">(solo aquello que no hayas elegido arriba)</span>
              <textarea class="img-notes" rows="2" placeholder="Ej.: luz de primera hora, muelle de carga, acero y madera, sin personas..."></textarea>
            </label>
            <button class="primary-button" type="button" data-action="generate-image" data-id="${id}">
              ${iconSvg("spark")}${img ? "Crear otra propuesta visual" : "Generar primera propuesta visual"}
            </button>
          </div>
        </div>
      </details>
    </section>
  `;
}

function iconSvg(name) {
  const paths = {
    spark: '<path d="M12 2l1.6 5.2L19 9l-5.4 1.8L12 16l-1.6-5.2L5 9l5.4-1.8L12 2z"/><path d="M5 14l.8 2.7L8.5 18l-2.7.8L5 22l-.8-3.2L1.5 18l2.7-1.3L5 14z"/>',
    menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
    layout: '<path d="M3 4h18v5H3z"/><path d="M3 13h7v7H3z"/><path d="M14 13h7v7h-7z"/>',
    folder: '<path d="M3 6h7l2 2h9v11H3z"/><path d="M3 10h18"/>',
    target: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4"/><path d="M12 2v4M12 18v4M2 12h4M18 12h4"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v6l4 2"/>',
    calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/><path d="M8 14h.01M12 14h.01M16 14h.01M8 18h.01M12 18h.01"/>',
    settings: '<path d="M12 8a4 4 0 100 8 4 4 0 000-8z"/><path d="M4 12h2M18 12h2M12 4v2M12 18v2M6.3 6.3l1.4 1.4M16.3 16.3l1.4 1.4M17.7 6.3l-1.4 1.4M7.7 16.3l-1.4 1.4"/>',
    refresh: '<path d="M20 6v6h-6"/><path d="M4 18v-6h6"/><path d="M18 9a7 7 0 00-11.8-2.5L4 9"/><path d="M6 15a7 7 0 0011.8 2.5L20 15"/>',
    alert: '<path d="M12 3l10 18H2L12 3z"/><path d="M12 9v5M12 17h.01"/>',
    copy: '<rect x="8" y="8" width="11" height="11" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V5a2 2 0 012-2h8a2 2 0 012 2v1"/>',
    check: '<path d="M20 6L9 17l-5-5"/>',
    send: '<path d="M22 2L11 13"/><path d="M22 2l-7 20-4-9-9-4 20-7z"/>',
    undo: '<path d="M9 14L4 9l5-5"/><path d="M4 9h10a6 6 0 010 12h-2"/>',
    trash: '<path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M6 6l1 15h10l1-15"/><path d="M10 11v6M14 11v6"/>',
    upload: '<path d="M12 16V4"/><path d="M7 9l5-5 5 5"/><path d="M4 20h16"/>',
    download: '<path d="M12 3v12"/><path d="M7 10l5 5 5-5"/><path d="M4 21h16"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    save: '<path d="M5 3h12l2 2v16H5z"/><path d="M8 3v6h8V3"/><path d="M8 21v-7h8v7"/>',
    image: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/>',
    expand: '<path d="M8 3H3v5M16 3h5v5M21 16v5h-5M3 16v5h5"/><path d="M8 8L3 3M16 8l5-5M16 16l5 5M8 16l-5 5"/>',
    chevron: '<path d="M9 18l6-6-6-6"/>',
    article: '<path d="M4 4h12l4 4v12H4z"/><path d="M16 4v4h4"/><path d="M8 12h8"/><path d="M8 16h8"/><path d="M8 8h4"/>',
  };
  return `<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${paths[name] || paths.spark}</svg>`;
}
