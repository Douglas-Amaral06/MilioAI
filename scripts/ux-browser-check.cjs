const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const demoPort = Number(process.env.UX_DEMO_PORT || 5173);
const realPort = Number(process.env.UX_REAL_PORT || 5174);
const demoOrigin = `http://127.0.0.1:${demoPort}`;
const realOrigin = `http://127.0.0.1:${realPort}`;
const regionSelector = '[aria-label="Conteúdo da conversa"]';
const now = "2026-10-20T12:00:00Z";
const message = (id, role, content, status = "complete") => ({
  id,
  role,
  content,
  status,
  created_at: now,
  sources: [],
});
const conversation = (id, title, messages = []) => ({
  id,
  title,
  messages,
  created_at: now,
  updated_at: now,
  topic_id: null,
  support_state: {},
});
async function settled(page) {
  await page.waitForFunction(() => {
    const field = document.querySelector("#message");
    return field && !field.disabled;
  });
}
async function atEnd(page) {
  await page.waitForFunction((selector) => {
    const e = document.querySelector(selector);
    return e && e.scrollHeight - e.clientHeight - e.scrollTop <= 2;
  }, regionSelector);
}
async function startServer(mode, port) {
  const server = spawn(
    process.execPath,
    [
      "node_modules/vite/bin/vite.js",
      "--mode",
      mode,
      "--host",
      "127.0.0.1",
      "--port",
      String(port),
    ],
    { cwd: path.resolve(__dirname, ".."), windowsHide: true },
  );
  let output = "";
  server.stdout.on("data", (chunk) => (output += chunk));
  server.stderr.on("data", (chunk) => (output += chunk));
  for (let i = 0; i < 150; i++) {
    if (server.exitCode !== null) throw new Error(output);
    if (output.includes("Local:")) return server;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  server.kill();
  throw new Error(`Vite não iniciou: ${output}`);
}

async function offlineUX(browser) {
  const server = await startServer("offline", demoPort);
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    permissions: ["clipboard-read", "clipboard-write"],
    serviceWorkers: "block",
  });
  context.setDefaultTimeout(10000);
  const forbidden = [],
    errors = [];
  const answer =
    "**Resposta recuperada**\n\nPrimeiro parágrafo.\nSegunda linha.\n\n- Item um\n- Item dois\n\n1. Etapa um\n2. Etapa dois\n\n[Portal](https://example.com) [fonte:internal-sentinel]";
  const expectedCopy =
    "Resposta recuperada\n\nPrimeiro parágrafo.\nSegunda linha.\n\n- Item um\n- Item dois\n\n1. Etapa um\n2. Etapa dois\n\nPortal (https://example.com) ";
  const messages = Array.from({ length: 6 }, (_, i) => [
    message(`user-${i}`, "user", `Mensagem antiga ${i}`),
    message(
      `assistant-${i}`,
      "assistant",
      "Parágrafo longo do histórico, usado somente para validar a leitura e a rolagem.\n\n".repeat(
        15,
      ),
    ),
  ]).flat();
  const lastMessage = message("recovered", "assistant", answer);
  lastMessage.sources = [
    {
      id: "hidden-source",
      title: "Fonte que não deve ser copiada",
      version: "test",
      excerpt: "METADATA_SENTINEL",
      is_test: true,
    },
  ];
  messages.push(lastMessage);
  const db = {
    version: 1,
    conversations: [
      conversation("ux-history", "Histórico UX", messages),
      conversation("ux-empty", "Outra conversa"),
    ],
  };
  try {
    await context.route("**/*", (route) => {
      const url = new URL(route.request().url());
      if (url.origin !== demoOrigin || url.pathname.startsWith("/api")) {
        forbidden.push(url.href);
        return route.abort();
      }
      return route.continue();
    });
    await context.addInitScript((database) => {
      if (!localStorage.getItem("milioai.demo.offline.v1"))
        localStorage.setItem(
          "milioai.demo.offline.v1",
          JSON.stringify(database),
        );
    }, db);
    const page = await context.newPage();
    await page.emulateMedia({ reducedMotion: "no-preference" });
    page.on("pageerror", (error) => errors.push(String(error)));
    page.on("dialog", (dialog) => {
      errors.push("Unexpected native dialog");
      void dialog.dismiss();
    });
    await page.goto(demoOrigin);
    await settled(page);
    await atEnd(page);
    const region = page.locator(regionSelector);
    const latest = page.getByRole("button", {
      name: "Ir para a última mensagem",
    });
    const last = () =>
      page.getByRole("article", { name: "Resposta do MilioAI" }).last();
    const copy = last().getByRole("button", { name: "Copiar resposta" });
    assert.equal(await latest.count(), 0);
    assert.equal(
      await page
        .getByRole("article", { name: "Mensagem de você" })
        .getByRole("button", { name: "Copiar resposta" })
        .count(),
      0,
    );
    const original = await last().innerText();
    const copyPath = await copy.locator("path").getAttribute("d");
    // The action is keyboard accessible even when concealed by the desktop hover rule.
    await copy.focus();
    await page.waitForFunction(
      () => getComputedStyle(document.activeElement).opacity === "1",
    );
    await copy.press("Enter");
    await last().getByText("Copiado", { exact: true }).waitFor();
    assert.equal(
      (await page.evaluate(() => navigator.clipboard.readText())).replace(
        /\r\n/g,
        "\n",
      ),
      expectedCopy,
    );
    assert.notEqual(await copy.locator("path").getAttribute("d"), copyPath);
    await last()
      .getByText("Copiado", { exact: true })
      .waitFor({ state: "hidden" });
    assert.equal(await copy.locator("path").getAttribute("d"), copyPath);
    assert.equal(await last().innerText(), original);
    await page.evaluate(() => {
      window.nativeClipboard = navigator.clipboard;
      window.nativeWrite = navigator.clipboard.writeText.bind(
        navigator.clipboard,
      );
      navigator.clipboard.writeText = () =>
        Promise.reject(
          new DOMException("Permission denied", "NotAllowedError"),
        );
    });
    await copy.click();
    await last()
      .getByText("Não foi possível copiar", { exact: true })
      .waitFor();
    await page.evaluate(() =>
      Object.defineProperty(navigator, "clipboard", {
        configurable: true,
        value: undefined,
      }),
    );
    await copy.click();
    await last()
      .getByText("Não foi possível copiar", { exact: true })
      .waitFor();
    await page.evaluate(() => {
      Object.defineProperty(navigator, "clipboard", {
        configurable: true,
        value: window.nativeClipboard,
      });
      navigator.clipboard.writeText = window.nativeWrite;
    });
    const longAnswer = page
      .getByRole("article", { name: "Resposta do MilioAI" })
      .first();
    await longAnswer.getByRole("button", { name: "Copiar resposta" }).click();
    await longAnswer.getByText("Copiado", { exact: true }).waitFor();
    assert.equal(
      (await page.evaluate(() => navigator.clipboard.readText())).replace(
        /\r\n/g,
        "\n",
      ),
      messages[1].content,
    );
    await latest.waitFor();
    await latest.click();
    await atEnd(page);
    console.log(
      "PASS: clipboard real, quebras/listas/links, histórico, confirmação e falhas de permissão/API ausente",
    );

    await region.evaluate((e) => (e.scrollTop = 0));
    await latest.waitFor();
    const input = page.getByRole("textbox", { name: "Sua mensagem" });
    const jumpBox = await latest.boundingBox();
    const composerBox = await input.locator("..").boundingBox();
    assert.ok(jumpBox.y + jumpBox.height <= composerBox.y);
    await page.evaluate(() => {
      const originalScroll = Element.prototype.scrollTo;
      window.scrollCalls = [];
      Element.prototype.scrollTo = function (options) {
        window.scrollCalls.push(options.behavior);
        return originalScroll.call(this, options);
      };
    });
    await latest.click();
    await atEnd(page);
    await latest.waitFor({ state: "hidden" });
    assert.equal(
      await page.evaluate(() => window.scrollCalls.at(-1)),
      "smooth",
    );
    await page.emulateMedia({ reducedMotion: "reduce" });
    await region.evaluate((e) => (e.scrollTop = 0));
    await latest.waitFor();
    await latest.click();
    await atEnd(page);
    assert.equal(
      await page.evaluate(() => window.scrollCalls.at(-1)),
      "instant",
    );
    await page.emulateMedia({ reducedMotion: "no-preference" });
    const controls = page.getByRole("region", {
      name: "Demonstração local",
      exact: true,
    });
    await controls.getByRole("combobox").selectOption("slow");
    async function startResponse() {
      await input.fill("Mensagem para testar streaming");
      await input.press("Enter");
      await page
        .getByText("MilioAI está preparando a resposta…", { exact: true })
        .waitFor();
    }
    await startResponse();
    await atEnd(page);
    await page.getByText("Respondendo…", { exact: true }).waitFor();
    await settled(page);
    await atEnd(page);
    assert.equal(await latest.count(), 0);
    // Sending from old history reveals the user's new message, then reading can resume.
    await region.evaluate((e) => (e.scrollTop = 0));
    await latest.waitFor();
    await startResponse();
    await atEnd(page);
    await region.evaluate((e) => (e.scrollTop = 0));
    await latest.waitFor();
    const readingTop = await region.evaluate((e) => e.scrollTop);
    await settled(page);
    assert.ok(
      Math.abs((await region.evaluate((e) => e.scrollTop)) - readingTop) <= 2,
    );
    assert.ok(await latest.isVisible());
    await latest.click();
    await atEnd(page);
    assert.equal(await page.evaluate(() => window.scrollY), 0);
    assert.equal(
      await page.evaluate(() => document.documentElement.scrollTop),
      0,
    );
    console.log(
      "PASS: retorno suave, movimento reduzido, streaming, leitura preservada e envio a partir do histórico",
    );

    await page
      .getByRole("button", { name: "Outra conversa", exact: true })
      .click();
    await page
      .getByRole("heading", {
        name: "Como posso ajudar?",
      })
      .waitFor();
    assert.equal(await latest.count(), 0);
    await page
      .getByRole("button", { name: "Histórico UX", exact: true })
      .click();
    await last().waitFor();
    await atEnd(page);
    await page
      .getByRole("searchbox", { name: "Buscar conversas pelo título" })
      .fill("não existe");
    await page
      .getByText("Nenhuma conversa encontrada.", { exact: true })
      .waitFor();
    await page
      .getByRole("searchbox", { name: "Buscar conversas pelo título" })
      .fill("");
    await page.reload();
    await settled(page);
    await atEnd(page);
    await last().getByRole("button", { name: "Copiar resposta" }).click();
    await last().getByText("Copiado", { exact: true }).waitFor();

    fs.mkdirSync("tmp/ux-qa", { recursive: true });
    for (const [width, height] of [
      [1440, 900],
      [1366, 768],
      [768, 1024],
      [390, 844],
      [390, 400],
    ]) {
      await page.setViewportSize({ width, height });
      await region.evaluate((e) => (e.scrollTop = 0));
      await latest.waitFor();
      assert.ok(
        await page.evaluate(
          () =>
            document.documentElement.scrollWidth <= innerWidth &&
            document.documentElement.scrollHeight <= innerHeight,
        ),
      );
      const button = await latest.boundingBox();
      const field = await input.boundingBox();
      assert.ok(button.y >= 0 && button.y + button.height <= field.y);
      assert.ok(field.y + field.height <= height);
      await page.screenshot({ path: `tmp/ux-qa/chat-${width}-${height}.png` });
    }
    const mobile = await browser.newContext({
      viewport: { width: 390, height: 844 },
      hasTouch: true,
      isMobile: true,
      storageState: await context.storageState(),
    });
    await mobile.route("**/*", (route) =>
      new URL(route.request().url()).origin === demoOrigin
        ? route.continue()
        : route.abort(),
    );
    const touchPage = await mobile.newPage();
    await touchPage.goto(demoOrigin);
    await settled(touchPage);
    await atEnd(touchPage);
    assert.equal(
      await touchPage
        .getByRole("button", { name: "Copiar resposta" })
        .last()
        .evaluate((e) => getComputedStyle(e).opacity),
      "1",
    );
    await touchPage.screenshot({ path: "tmp/ux-qa/touch.png" });
    await mobile.close();
    assert.deepEqual(forbidden, []);
    assert.deepEqual(errors, []);
    console.log(
      "PASS: troca de conversa, busca vazia, recarga, cinco viewports, toque e zero chamadas externas/API",
    );
  } finally {
    await context.close();
    server.kill();
  }
}

async function requestUX(browser) {
  const server = await startServer("development", realPort);
  const context = await browser.newContext({
    viewport: { width: 1366, height: 768 },
    serviceWorkers: "block",
  });
  context.setDefaultTimeout(10000);
  let rows = [],
    streams = 0,
    mode = "reject",
    release;
  let instructors = [],
    cards = [];
  const errors = [],
    forbidden = [];
  async function waitStream(count) {
    const deadline = Date.now() + 10000;
    while (streams < count) {
      if (Date.now() > deadline)
        throw new Error(`Stream ${count} não foi iniciado`);
      await new Promise((resolve) => setTimeout(resolve, 20));
    }
  }
  try {
    await context.route("**/*", async (route) => {
      const req = route.request();
      const url = new URL(req.url());
      if (url.origin !== realOrigin) {
        forbidden.push(url.href);
        return route.abort();
      }
      if (!url.pathname.startsWith("/api/v1/")) return route.continue();
      const parts = url.pathname.replace("/api/v1/", "").split("/");
      const json = (value) => route.fulfill({ status: 200, json: value });
      if (parts[0] === "me") return json({ id: "test-user" });
      if (parts[0] === "support")
        return json(
          parts[1] === "instructors"
            ? instructors
            : parts[1] === "transport-cards"
              ? cards
              : [],
        );
      if (parts[0] !== "conversations")
        throw new Error(`Unexpected API path ${url.pathname}`);
      if (parts.length === 1) {
        if (req.method() === "POST") {
          const row = conversation("request-ux", "Nova conversa");
          rows.push(row);
          return json(row);
        }
        return json(rows);
      }
      const row = rows.find((c) => c.id === parts[1]);
      if (parts.length === 2) return json(row);
      if (parts[2] === "messages") return json(row.messages);
      if (parts[2] === "attachments") return json([]);
      if (parts[2] !== "stream")
        throw new Error(`Unexpected API path ${url.pathname}`);
      streams++;
      const payload = req.postDataJSON();
      await new Promise((resolve) => (release = resolve));
      if (mode === "reject")
        return route.fulfill({
          status: 503,
          json: { message: "Traceback internal-server secret=DO_NOT_SHOW" },
        });
      const user = message(`user-${streams}`, "user", payload.content);
      const assistant = message(
        `assistant-${streams}`,
        "assistant",
        "",
        "processing",
      );
      const frames = [{ event: "start", user, assistant: { ...assistant } }];
      if (mode === "error") {
        assistant.status = "failed";
        assistant.content = "Resposta não concluída.";
        frames.push({
          event: "error",
          message: "Traceback internal-server secret=DO_NOT_SHOW",
          code: "internal_failure",
        });
      } else {
        assistant.status = "complete";
        assistant.content =
          "Resposta confirmada. [Portal](https://conectajovem.dema.org.br/)";
        frames.push(
          { event: "delta", text: assistant.content },
          { event: "done", message: assistant },
        );
      }
      row.messages.push(user, assistant);
      return route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: frames.map((e) => `data: ${JSON.stringify(e)}\n\n`).join(""),
      });
    });
    const page = await context.newPage();
    page.on("pageerror", (e) => errors.push(String(e)));
    await page.goto(realOrigin);
    await settled(page);
    const input = page.getByRole("textbox", { name: "Sua mensagem" });
    const form = input.locator("..");
    const draft = "Rascunho importante\nPreservar antes da confirmação";
    await input.fill(draft);
    const before = await input.boundingBox();
    await page
      .getByRole("button", { name: "Enviar mensagem", exact: true })
      .click();
    await page.waitForFunction(() =>
      document.body.innerText.includes("Enviando mensagem…"),
    );
    await waitStream(1);
    assert.equal(await input.inputValue(), draft);
    assert.ok(await input.isDisabled());
    const pendingBox = await input.boundingBox();
    assert.equal(pendingBox.y, before.y);
    assert.equal(pendingBox.height, before.height);
    // Exercise the synchronous guard, including form submission without a button click.
    await form.evaluate((e) => {
      e.requestSubmit();
      e.requestSubmit();
    });
    await page.waitForFunction(
      () =>
        document.querySelector("button[aria-label='Enviando mensagem']") !==
        null,
    );
    assert.equal(streams, 1);
    assert.equal(rows.length, 1);
    release();
    await settled(page);
    assert.equal(await input.inputValue(), draft);
    assert.equal(await page.locator("article").count(), 0);
    assert.match(
      await page.getByRole("alert").innerText(),
      /Não foi possível concluir sua solicitação/,
    );
    assert.doesNotMatch(
      await page.locator("body").innerText(),
      /Traceback|DO_NOT_SHOW|internal-server/,
    );
    mode = "success";
    await page
      .getByRole("button", { name: "Enviar mensagem", exact: true })
      .click();
    await waitStream(2);
    release();
    await settled(page);
    assert.equal(await input.inputValue(), "");
    assert.equal(
      await page.getByRole("article", { name: "Mensagem de você" }).count(),
      1,
    );
    assert.equal(
      await page
        .getByRole("link", { name: "Portal", exact: true })
        .getAttribute("href"),
      "https://conectajovem.dema.org.br/",
    );
    mode = "error";
    await input.fill("Falha após confirmação");
    await input.press("Enter");
    await waitStream(3);
    release();
    await settled(page);
    assert.match(
      await page.getByRole("alert").innerText(),
      /Não foi possível concluir a resposta/,
    );
    assert.doesNotMatch(
      await page.locator("body").innerText(),
      /Traceback|DO_NOT_SHOW|internal-server/,
    );
    assert.equal(await page.locator("article").count(), 4);
    assert.equal(
      await page
        .getByRole("button", { name: "Tentar novamente", exact: true })
        .count(),
      0,
    );
    mode = "success";
    await input.fill("Continuar após falha");
    await input.press("Enter");
    await waitStream(4);
    release();
    await settled(page);
    assert.equal(await page.locator("article").count(), 6);
    rows[0].support_state = { asked: true, stage: "selection" };
    await page.reload();
    await settled(page);
    await page
      .getByText("Nenhum instrutor disponível no momento.", { exact: true })
      .waitFor();
    instructors = [{ id: "one", name: "Ana Teste" }];
    await page.reload();
    await settled(page);
    await page
      .getByRole("searchbox", { name: "Buscar instrutor pelo nome" })
      .fill("ausente");
    await page
      .getByText("Nenhum instrutor encontrado. Tente outro nome.", {
        exact: true,
      })
      .waitFor();
    rows[0].support_state = { vt_stage: "selection" };
    await page.reload();
    await settled(page);
    await page
      .getByText("Nenhum cartão disponível no momento.", { exact: true })
      .waitFor();
    cards = [{ code: "one", name: "Cartão Teste", uf: "SP" }];
    await page.reload();
    await settled(page);
    await page
      .getByRole("searchbox", { name: "Buscar cartão ou operadora" })
      .fill("ausente");
    await page
      .getByText("Nenhum cartão encontrado. Tente outro cartão ou operadora.", {
        exact: true,
      })
      .waitFor();
    assert.deepEqual(errors, []);
    assert.deepEqual(forbidden, []);
    console.log(
      "PASS: confirmação de envio, rascunho em falha, composer estável, bloqueio duplicado, erros seguros, continuidade, listas vazias e links",
    );
  } finally {
    if (release) release();
    await context.close();
    server.kill();
  }
}

async function run() {
  const browser = await chromium.launch({
    channel: process.env.PLAYWRIGHT_CHANNEL || "msedge",
    headless: true,
  });
  try {
    await offlineUX(browser);
    await requestUX(browser);
    console.log("UX BROWSER: PASS");
  } finally {
    await browser.close();
  }
}
run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
