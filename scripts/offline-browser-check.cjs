const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const port = Number(process.env.OFFLINE_TEST_PORT || 5173);
const origin = `http://127.0.0.1:${port}`;
async function run() {
  const server = spawn(
    process.execPath,
    [
      "node_modules/vite/bin/vite.js",
      "--mode",
      "offline",
      "--host",
      "127.0.0.1",
      "--port",
      String(port),
      "--strictPort",
    ],
    { cwd: path.resolve(__dirname, ".."), windowsHide: true },
  );
  let output = "";
  server.stdout.on("data", (chunk) => (output += chunk));
  server.stderr.on("data", (chunk) => (output += chunk));
  let browser;
  try {
    let ready = false;
    for (let i = 0; i < 100; i++) {
      if (server.exitCode !== null) throw new Error(output);
      if (output.includes("Local:")) {
        ready = true;
        break;
      }
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
    assert.ok(ready, output);
    browser = await chromium.launch({
      channel: process.env.PLAYWRIGHT_CHANNEL || "msedge",
      headless: true,
    });
    const context = await browser.newContext({
      serviceWorkers: "block",
      viewport: { width: 1440, height: 900 },
    });
    const forbidden = [],
      errors = [];
    await context.route("**/*", (route) => {
      const url = new URL(route.request().url());
      if (url.origin !== origin || url.pathname.startsWith("/api")) {
        forbidden.push(url.href);
        return route.abort();
      }
      return route.continue();
    });
    const page = await context.newPage();
    page.on("pageerror", (error) => errors.push(String(error)));
    await page.goto(origin);
    const controls = page.getByRole("region", {
      name: "Demonstração local",
      exact: true,
    });
    await controls.waitFor();
    const input = page.getByRole("textbox", { name: "Sua mensagem" });
    const last = () =>
      page.getByRole("article", { name: "Resposta do MilioAI" }).last();
    async function settled() {
      await page.waitForFunction(() => {
        const field = document.querySelector("#message");
        return field && !field.disabled;
      });
    }
    async function send(text = "Mensagem demonstrativa") {
      await input.fill(text);
      await input.press("Enter");
      await settled();
    }
    async function click(name) {
      await page.getByRole("button", { name, exact: true }).click();
      await settled();
    }
    await settled();
    await page.evaluate(() => {
      localStorage.setItem("milioai.workspace.v1", "preservar-real");
      sessionStorage.setItem(
        "milioai.auth.session.v1",
        JSON.stringify({
          access_token: "real-sentinel",
          refresh_token: "real-refresh",
          expires_at: 1,
        }),
      );
    });
    assert.equal(
      await page.getByLabel("Assuntos disponíveis").getByRole("button").count(),
      8,
    );
    assert.ok(
      await page.getByRole("button", { name: "Anexar arquivos" }).isDisabled(),
    );
    await page.getByRole("button", { name: /Folha Ponto/ }).click();
    await settled();
    await click("Qual é o prazo de entrega da folha ponto?");
    assert.match(await last().innerText(), /Conteúdo demonstrativo/);
    await controls.getByRole("combobox").selectOption("sources");
    await send();
    await last().getByText("Fontes consultadas (1)").click();
    assert.match(await last().innerText(), /Guia demonstrativo local/);
    assert.equal(
      await last()
        .getByRole("link", { name: "Abrir demonstração local" })
        .getAttribute("href"),
      "http://127.0.0.1:5173/#message",
    );
    await page.reload();
    await settled();
    assert.equal(await page.locator("article").count(), 4);
    await page.getByText("Fazer outra pergunta", { exact: false }).click();
    await click("← Voltar aos assuntos");
    await page.getByRole("button", { name: /Falta no Curso/ }).click();
    await settled();
    await click("Como descubro quem é meu instrutor?");
    await click("Sim, sei quem é.");
    const search = page.getByRole("searchbox", {
      name: "Buscar instrutor pelo nome",
    });
    await search.fill("ana");
    assert.equal(
      await page
        .getByLabel("Instrutores disponíveis")
        .getByRole("listitem")
        .count(),
      1,
    );
    await click("Ana Exemplo");
    assert.match(await last().innerText(), /ana@example.invalid/);
    await click("Voltar à lista de instrutores");
    await search.fill("bruno");
    await click("Bruno Demonstração");
    assert.match(await last().innerText(), /contato não informado/);
    await click("Voltar à lista de instrutores");
    await click("Cancelar seleção");
    await page.getByText("Fazer outra pergunta", { exact: false }).click();
    await click("← Voltar aos assuntos");
    await page
      .getByRole("button", { name: /Benefício Vale-Transporte/ })
      .click();
    await settled();
    await click(
      "Como solicito a segunda via do meu cartão de vale-transporte?",
    );
    const cards = page.getByRole("searchbox", {
      name: "Buscar cartão ou operadora",
    });
    await cards.fill("aurora");
    assert.equal(
      await page
        .getByLabel("Cartões disponíveis")
        .getByRole("listitem")
        .count(),
      1,
    );
    await page.getByRole("button", { name: /Cartão Aurora/ }).click();
    await settled();
    assert.match(await last().innerText(), /Aurora/);
    await click("Trocar cartão de transporte");
    await cards.fill("modelo");
    await page.getByRole("button", { name: /Cartão Horizonte/ }).click();
    await settled();
    assert.match(await last().innerText(), /Horizonte/);
    await controls.getByRole("combobox").selectOption("error");
    await send();
    assert.match(await last().innerText(), /Falha controlada/);
    await controls.getByRole("combobox").selectOption("slow");
    await input.fill("Cancelar exemplo");
    await input.press("Enter");
    await page
      .getByText("MilioAI está preparando a resposta…", { exact: true })
      .waitFor();
    await controls
      .getByRole("button", { name: "Cancelar processamento" })
      .click();
    await settled();
    assert.match(await last().innerText(), /foi interrompida/);
    await page
      .getByRole("button", { name: "Nova conversa", exact: true })
      .first()
      .click();
    await settled();
    await page
      .getByRole("button", { name: /Renomear Nova conversa/ })
      .first()
      .click();
    await page
      .getByRole("textbox", { name: "Título da conversa" })
      .fill("Conversa QA");
    await click("Salvar título");
    await page
      .getByRole("button", { name: "Nova conversa", exact: true })
      .last()
      .click();
    await settled();
    await page.locator("article").first().waitFor();
    assert.ok((await page.locator("article").count()) > 0);
    await click("Conversa QA");
    await page.locator("article").first().waitFor({ state: "hidden" });
    assert.equal(await page.locator("article").count(), 0);
    await page
      .getByRole("button", { name: "Excluir Conversa QA", exact: true })
      .click();
    await click("Excluir conversa");
    await page.getByText("Fazer outra pergunta", { exact: false }).click();
    await click("← Voltar aos assuntos");
    await page.getByRole("button", { name: /08 Outros/ }).click();
    await settled();
    await controls.getByRole("combobox").selectOption("long");
    await send();
    assert.match(await last().innerText(), /Exemplo 8/);
    await controls.getByRole("combobox").selectOption("empty");
    await send();
    assert.match(await last().innerText(), /Não há informações disponíveis/);
    for (const [width, height] of [
      [1440, 900],
      [390, 844],
    ]) {
      await page.setViewportSize({ width, height });
      assert.ok(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      );
    }
    fs.mkdirSync("tmp/offline-qa", { recursive: true });
    await page.screenshot({ path: "tmp/offline-qa/mobile.png" });
    await Promise.all([
      page.waitForEvent("load"),
      controls.getByRole("button", { name: "Limpar demonstração" }).click(),
    ]);
    await settled();
    assert.equal(await page.locator("article").count(), 0);
    assert.equal(
      await page.evaluate(() => localStorage.getItem("milioai.workspace.v1")),
      "preservar-real",
    );
    assert.match(
      await page.evaluate(() =>
        sessionStorage.getItem("milioai.auth.session.v1"),
      ),
      /real-sentinel/,
    );
    assert.deepEqual(forbidden, []);
    assert.deepEqual(errors, []);
    console.log(
      JSON.stringify(
        {
          result: "PASS",
          forbiddenRequests: forbidden,
          pageErrors: errors,
          checks:
            "topics, guided questions, streaming, sources, reload, instructor search/contact/missing/cancel, card search/switch, failure, cancellation, conversations CRUD, Outros, long answer, responsive, isolated reset",
        },
        null,
        2,
      ),
    );
  } finally {
    if (browser) await browser.close();
    server.kill();
  }
}
run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
