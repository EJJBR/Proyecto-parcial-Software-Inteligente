(() => {
  "use strict";

  const form = document.querySelector("#message-form");
  const input = document.querySelector("#message-input");
  const counter = document.querySelector("#message-counter");
  const sendButton = document.querySelector("#send-button");
  const chatMessages = document.querySelector("#chat-messages");
  const catalogProducts = document.querySelector("#catalog-products");
  const catalogStatus = document.querySelector("#catalog-status");
  const catalogCount = document.querySelector("#catalog-count");
  const searchInput = document.querySelector("#product-search");
  const categoryFilters = document.querySelector("#category-filters");
  const notice = document.querySelector("#app-notice");
  const recommendationEmpty = document.querySelector("#recommendation-empty");
  const recommendationResult = document.querySelector("#recommendation-result");
  const recommendationRows = document.querySelector("#recommendation-products");
  const recommendationSource = document.querySelector("#recommendation-source");
  const fallbackDetails = document.querySelector("#fallback-details");
  const fallbackReason = document.querySelector("#fallback-reason");
  const understoodHint = document.querySelector("#understood-hint");
  const selectedCategory = { value: "Todos" };
  const categoryLabels = Object.freeze({
    abarrotes: "abarrotes",
    bebidas: "bebidas",
    lacteos: "lácteos",
    limpieza: "limpieza",
    panaderia: "panadería",
    snacks: "snacks",
  });
  let products = [];
  let busy = false;

  const money = (value) => {
    const amount = Number(value);
    if (!Number.isFinite(amount)) return "S/ 0.00";
    return `S/ ${amount.toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  };

  const categoryIcon = (category) => {
    const normalized = String(category || "").toLocaleLowerCase("es");
    if (normalized.includes("láct") || normalized.includes("lact")) return "🥛";
    if (normalized.includes("bebida")) return "🥤";
    if (normalized.includes("snack")) return "🍿";
    if (normalized.includes("abarrote")) return "🌾";
    if (normalized.includes("limpieza")) return "🧹";
    if (normalized.includes("cuidado") || normalized.includes("higiene")) return "🧼";
    return "🛍️";
  };

  const scrollChatToBottom = () => {
    chatMessages.scrollTop = chatMessages.scrollHeight;
  };

  const addMessage = (text, role = "assistant", options = {}) => {
    const row = document.createElement("div");
    row.className = `message-row ${role}${options.error ? " error" : ""}`;

    const avatar = document.createElement("span");
    avatar.className = "message-avatar";
    avatar.setAttribute("aria-hidden", "true");
    avatar.textContent = role === "user" ? "🙂" : "🛒";

    const bubble = document.createElement("div");
    bubble.className = "message-bubble";
    bubble.textContent = String(text ?? "");

    if (options.pending) {
      const indicator = document.createElement("span");
      indicator.className = "typing-indicator";
      indicator.setAttribute("role", "status");
      indicator.textContent = "Calculando tu recomendación…";
      const dots = document.createElement("span");
      dots.className = "typing-dots";
      dots.setAttribute("aria-hidden", "true");
      for (let index = 0; index < 3; index += 1) {
        dots.append(document.createElement("span"));
      }
      indicator.append(dots);
      bubble.replaceChildren(indicator);
    } else {
      const time = document.createElement("span");
      time.className = "message-time";
      time.textContent = new Intl.DateTimeFormat("es-PE", {
        hour: "2-digit",
        minute: "2-digit",
      }).format(new Date());
      bubble.append(document.createElement("br"), time);
    }

    if (role !== "user") row.append(avatar);
    row.append(bubble);
    chatMessages.append(row);
    scrollChatToBottom();
    return row;
  };

  const setBusy = (value) => {
    busy = value;
    sendButton.disabled = value;
    input.disabled = value;
    sendButton.querySelector("span:first-child").textContent = value ? "Enviando…" : "Enviar";
    form.setAttribute("aria-busy", String(value));
  };

  const setCounter = () => {
    const length = input.value.length;
    counter.textContent = `${length}/500`;
    counter.classList.toggle("is-near-limit", length >= 450);
  };

  const buildImage = (url, category, className) => {
    const wrapper = document.createElement("span");
    wrapper.className = className;
    if (url) {
      const image = document.createElement("img");
      image.src = url;
      image.alt = "";
      image.loading = "lazy";
      image.onerror = () => {
        wrapper.replaceChildren(document.createTextNode(categoryIcon(category)));
      };
      wrapper.append(image);
    } else {
      wrapper.textContent = categoryIcon(category);
    }
    return wrapper;
  };

  const addFilter = (category) => {
    const button = document.createElement("button");
    button.className = "filter-chip";
    button.type = "button";
    button.dataset.category = category;
    button.setAttribute("aria-pressed", "false");
    button.textContent = category;
    categoryFilters.append(button);
  };

  const renderCatalog = () => {
    const search = searchInput.value.trim().toLocaleLowerCase("es");
    const visible = products.filter((product) => {
      const matchesCategory = selectedCategory.value === "Todos"
        || product.categoria === selectedCategory.value;
      const matchesSearch = String(product.nombre || "").toLocaleLowerCase("es").includes(search);
      return matchesCategory && matchesSearch;
    });
    catalogProducts.replaceChildren();
    catalogCount.textContent = `${visible.length}`;
    if (!visible.length) {
      catalogStatus.hidden = false;
      catalogStatus.textContent = products.length
        ? "No hay productos que coincidan con la búsqueda."
        : "No hay productos disponibles.";
      return;
    }
    catalogStatus.hidden = true;

    visible.forEach((product) => {
      const card = document.createElement("article");
      card.className = "product-card";
      card.append(buildImage(product.imagen, product.categoria, "product-picture"));

      const copy = document.createElement("div");
      copy.className = "product-copy";
      const name = document.createElement("strong");
      name.className = "product-name";
      name.textContent = product.nombre;
      const meta = document.createElement("span");
      meta.className = "product-meta";
      const price = document.createElement("span");
      price.className = "product-price";
      price.textContent = money(product.precio_venta);
      const category = document.createElement("span");
      category.textContent = product.categoria;
      meta.append(price, category);
      copy.append(name, meta);

      const addButton = document.createElement("button");
      addButton.className = "add-product";
      addButton.type = "button";
      addButton.textContent = "+";
      addButton.setAttribute("aria-label", `Agregar ${product.nombre} a tu solicitud`);
      addButton.addEventListener("click", () => addProductToMessage(product.nombre));
      card.append(copy, addButton);
      catalogProducts.append(card);
    });
  };

  const loadCatalog = async () => {
    catalogStatus.hidden = false;
    catalogStatus.textContent = "Cargando catálogo…";
    try {
      const response = await fetch("/api/catalogo", {
        headers: { Accept: "application/json" },
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.mensaje || "No se pudo cargar el catálogo.");
      products = Array.isArray(data.productos) ? data.productos : [];
      const categories = Array.isArray(data.categorias) ? data.categorias : [];
      categoryFilters.replaceChildren();
      addFilter("Todos");
      categories.forEach(addFilter);
      renderCatalog();
    } catch (error) {
      catalogCount.textContent = "—";
      catalogStatus.hidden = false;
      catalogStatus.textContent = error instanceof Error
        ? error.message
        : "No se pudo cargar el catálogo. Inténtalo nuevamente.";
    }
  };

  const addProductToMessage = (productName) => {
    const phrase = `incluye ${productName}`;
    const existing = input.value.trim();
    const includesAlready = new RegExp(
      `(?:^|[,;\\n])\\s*${escapeRegExp(phrase)}\\s*(?=$|[,;\\n])`,
      "i",
    ).test(existing);
    if (!includesAlready) {
      input.value = existing ? `${existing.replace(/[,;\\s]+$/, "")}, ${phrase}` : phrase;
      setCounter();
    }
    input.focus();
  };

  const escapeRegExp = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

  const showRecommendation = (data) => {
    recommendationEmpty.hidden = true;
    recommendationResult.hidden = false;
    const usedAI = data.usada_ia === true;
    recommendationSource.textContent = usedAI ? "Basado en IA" : "Respaldo local";
    recommendationSource.classList.toggle("local", !usedAI);
    fallbackDetails.hidden = usedAI || !data.motivo_respaldo;
    fallbackReason.textContent = data.motivo_respaldo || "";
    document.querySelector("#recommendation-explanation").textContent = data.explicacion || "";
    recommendationRows.replaceChildren();

    (Array.isArray(data.productos) ? data.productos : []).forEach((product) => {
      const row = document.createElement("tr");
      const productCell = document.createElement("th");
      productCell.scope = "row";
      const productContent = document.createElement("span");
      productContent.className = "recommendation-product";
      productContent.append(
        buildImage(product.imagen, "", "recommendation-product-image"),
      );
      const name = document.createElement("span");
      name.className = "recommendation-product-name";
      name.textContent = product.nombre;
      productContent.append(name);
      productCell.append(productContent);

      const quantity = document.createElement("td");
      quantity.textContent = String(product.cantidad);
      const unitPrice = document.createElement("td");
      unitPrice.textContent = money(product.precio_unitario);
      const subtotal = document.createElement("td");
      subtotal.textContent = money(product.subtotal);
      row.append(productCell, quantity, unitPrice, subtotal);
      recommendationRows.append(row);
    });

    document.querySelector("#recommendation-total").textContent = money(data.costo_total);
    document.querySelector("#recommendation-budget").textContent = money(data.presupuesto);
    document.querySelector("#recommendation-leftover").textContent = money(
      Number(data.presupuesto) - Number(data.costo_total),
    );

    const understood = data.entendido || {};
    const priorities = Array.isArray(understood.categorias_prioritarias)
      ? understood.categorias_prioritarias
      : [];
    const included = Array.isArray(understood.incluir_forzado)
      ? understood.incluir_forzado
      : [];
    const excluded = Array.isArray(understood.excluir)
      ? understood.excluir
      : [];
    document.querySelector("#understood-budget").textContent =
      understood.presupuesto == null ? "—" : money(understood.presupuesto);
    document.querySelector("#understood-priority").textContent =
      priorities.length
        ? priorities.map((category) => categoryLabels[category] || category).join(", ")
        : "ninguna";
    document.querySelector("#understood-included").textContent =
      included.length ? included.join(", ") : "ninguno";
    document.querySelector("#understood-excluded").textContent =
      excluded.length ? excluded.join(", ") : "ninguno";
    understoodHint.hidden = included.length === 0 && excluded.length === 0;
  };

  const sendMessage = async (message) => {
    if (busy || !message.trim()) return;
    addMessage(message, "user");
    const pending = addMessage("", "assistant", { pending: true });
    setBusy(true);
    notice.textContent = "Calculando tu recomendación.";

    try {
      const response = await fetch("/api/solicitud", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({ mensaje: message }),
      });
      let data;
      try {
        data = await response.json();
      } catch {
        throw new Error("El servidor devolvió una respuesta que no se pudo leer.");
      }
      pending.remove();

      if (data.tipo === "aclaracion") {
        addMessage(data.pregunta || "¿Podrías darme un poco más de información?");
        input.value = "";
        setCounter();
        input.focus();
      } else if (data.tipo === "recomendacion" && response.ok) {
        showRecommendation(data);
        addMessage("Listo, aquí está tu recomendación.");
        input.value = "";
        setCounter();
        notice.textContent = "La recomendación está lista.";
      } else {
        let messageForUser = data.mensaje || "No se pudo procesar tu solicitud.";
        if (response.status === 429) {
          messageForUser = `${messageForUser} Espera unos segundos y vuelve a intentarlo.`;
        }
        addMessage(messageForUser, "assistant", { error: true });
        notice.textContent = messageForUser;
      }
    } catch (error) {
      pending.remove();
      const messageForUser = error instanceof TypeError
        ? "No se pudo conectar con el servidor. Revisa tu conexión e inténtalo nuevamente."
        : error instanceof Error
          ? error.message
          : "Ocurrió un problema inesperado. Inténtalo nuevamente.";
      addMessage(messageForUser, "assistant", { error: true });
      notice.textContent = messageForUser;
    } finally {
      setBusy(false);
    }
  };

  const resetConversation = async () => {
    if (busy) return;
    const button = document.querySelector("#new-conversation");
    button.disabled = true;
    try {
      const response = await fetch("/api/reiniciar", {
        method: "POST",
        headers: { Accept: "application/json" },
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.mensaje || "No se pudo reiniciar la conversación.");
      chatMessages.replaceChildren();
      addMessage("¡Hola! Soy tu asistente de compras. Cuéntame tu presupuesto y qué productos o categorías quieres priorizar.");
      input.value = "";
      setCounter();
      notice.textContent = "Nueva conversación iniciada.";
      input.focus();
    } catch (error) {
      const message = error instanceof Error
        ? error.message
        : "No se pudo reiniciar la conversación.";
      addMessage(message, "assistant", { error: true });
    } finally {
      button.disabled = false;
    }
  };

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const message = input.value.trim();
    if (!message || busy) return;
    if (message.length > 500) {
      addMessage("El mensaje no puede superar los 500 caracteres.", "assistant", { error: true });
      return;
    }
    sendMessage(message);
  });

  input.addEventListener("input", setCounter);
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  searchInput.addEventListener("input", renderCatalog);
  categoryFilters.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-category]");
    if (!button) return;
    selectedCategory.value = button.dataset.category;
    categoryFilters.querySelectorAll("button[data-category]").forEach((chip) => {
      const isActive = chip === button;
      chip.classList.toggle("is-active", isActive);
      chip.setAttribute("aria-pressed", String(isActive));
    });
    renderCatalog();
  });

  document.querySelectorAll(".example-chip").forEach((button) => {
    button.addEventListener("click", () => {
      if (busy) return;
      input.value = button.dataset.example;
      setCounter();
      sendMessage(input.value.trim());
    });
  });
  document.querySelector("#new-conversation").addEventListener("click", resetConversation);

  addMessage("¡Hola! Soy tu asistente de compras. Cuéntame tu presupuesto y qué productos o categorías quieres priorizar.");
  setCounter();
  loadCatalog();
})();
