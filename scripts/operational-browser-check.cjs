const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const portal =
  "https://conectajovem.dema.org.br/accounts/login/?next=/polo/1e677d8e-6e50-470a-b2d0-3c2051bc405a/";
async function run() {
  const browser = await chromium.launch({
    channel: process.env.PLAYWRIGHT_CHANNEL || "msedge",
    headless: true,
  });
  try {
    const page = await browser.newPage({
      viewport: { width: 1440, height: 900 },
      locale: "pt-BR",
    });
    const errors = [];
    page.on("pageerror", (e) => errors.push(String(e)));
    await page.goto(process.env.BASE_URL || "http://127.0.0.1:5173");
    await page
      .getByRole("button", { name: "Nova conversa", exact: true })
      .first()
      .click();
    await page
      .getByRole("heading", {
        name: "Como posso ajudar?",
      })
      .waitFor();
    const field = page.getByRole("textbox", { name: "Sua mensagem" });
    const flow = page.getByRole("region", {
      name: "Atendimento com instrutor",
    });
    async function settled() {
      await page.waitForFunction(
        () => !document.querySelector("#message").disabled,
        null,
        { timeout: 180000 },
      );
    }
    async function send(text) {
      const completed = page.waitForResponse(
        (r) => r.url().endsWith("/stream") && r.status() === 200,
        { timeout: 180000 },
      );
      await field.fill(text);
      await field.press("Enter");
      await completed;
      await settled();
    }
    async function action(name) {
      const completed = page.waitForResponse(
        (r) => r.url().endsWith("/stream") && r.status() === 200,
        { timeout: 180000 },
      );
      await flow.getByRole("button", { name, exact: true }).click();
      await completed;
      await settled();
    }
    await send("Faltei na capacitação. Onde mando meu atestado?");
    await flow
      .getByRole("button", { name: "Sim, sei quem é.", exact: true })
      .waitFor();
    const link = page
      .getByRole("link", { name: "Conecta Jovem", exact: true })
      .last();
    assert.equal(await link.getAttribute("href"), portal);
    assert.equal(
      await link.evaluate((e) => getComputedStyle(e).color),
      "rgb(64, 47, 221)",
    );
    assert.equal(await link.getAttribute("rel"), "noopener noreferrer");
    await action("Sim, sei quem é.");
    const search = flow.getByRole("searchbox", {
      name: "Buscar instrutor pelo nome",
    });
    await flow
      .getByRole("button", {
        name: "Marcio Frederico Oliveira da Silva",
        exact: true,
      })
      .waitFor();
    assert.equal(await flow.getByRole("listitem").count(), 16);
    assert.ok(!(await flow.innerText()).includes("@"));
    await page.reload();
    await search.waitFor();
    await search.fill("marcio");
    assert.equal(await flow.getByRole("listitem").count(), 1);
    await search.press("Tab");
    assert.equal(
      await page.evaluate(() => document.activeElement.textContent),
      "Marcio Frederico Oliveira da Silva",
    );
    await action("Marcio Frederico Oliveira da Silva");
    const mail = page.getByRole("link", {
      name: "marcio.silva@renapsi.org.br",
      exact: true,
    });
    await mail.waitFor();
    assert.equal(
      await mail.getAttribute("href"),
      "mailto:marcio.silva@renapsi.org.br",
    );
    await action("Voltar à lista de instrutores");
    await search.fill("leticia");
    await action("Letícia da Silva Lima");
    await page
      .getByRole("link", { name: "educacional.sp@renapsi.org.br", exact: true })
      .last()
      .waitFor();
    assert.ok(
      !(await page.locator("article").last().innerText()).includes("leticia@"),
    );
    await action("Voltar à lista de instrutores");
    await action("Não sei quem é.");
    assert.equal(
      await page
        .getByRole("link", { name: "11 99803-0631", exact: true })
        .last()
        .getAttribute("href"),
      "tel:+5511998030631",
    );
    await action("Voltar à lista de instrutores");
    await send("Onde baixo meu holerite?");
    await search.waitFor({ state: "hidden" });
    assert.ok(
      (await page.locator("article").last().innerText()).includes("holerite"),
    );
    await send("Onde mando meu atestado do curso?");
    assert.ok(
      !(await page.locator("article").last().innerText()).includes(
        "Você sabe quem é",
      ),
    );
    await action("Voltar à lista de instrutores");
    await action("Cancelar seleção");
    await search.waitFor({ state: "hidden" });
    await send("Preciso entregar meu documento.");
    assert.ok(
      (await page.locator("article").last().innerText()).includes(
        "Qual documento",
      ),
    );
    await send("Qual o prazo da folha ponto?");
    await page
      .locator("article")
      .last()
      .getByText(/Fontes consultadas/)
      .waitFor();
    fs.mkdirSync("tmp/operational-qa", { recursive: true });
    for (const [width, height] of [
      [1440, 900],
      [1366, 768],
      [390, 844],
      [390, 400],
    ]) {
      await page.setViewportSize({ width, height });
      await page.waitForTimeout(150);
      assert.ok(
        await page.evaluate(
          () =>
            document.documentElement.scrollWidth <= innerWidth &&
            document.documentElement.scrollHeight <= innerHeight,
        ),
      );
      const box = await field.boundingBox();
      assert.ok(box.y >= 0 && box.y + box.height <= height);
      await page.screenshot({
        path: `tmp/operational-qa/chat-${width}-${height}.png`,
      });
    }
    await page.setViewportSize({ width: 390, height: 844 });
    await action("Voltar à lista de instrutores");
    await search.fill("vinicius");
    await flow
      .getByRole("button", { name: "Vinícius Willians Maia", exact: true })
      .waitFor();
    await page.screenshot({
      path: "tmp/operational-qa/instructors-mobile.png",
    });
    assert.deepEqual(errors, []);
    console.log(
      JSON.stringify(
        {
          result: "PASS",
          checks: [
            "real semantic course routing",
            "exact institutional link and color",
            "16 names without email",
            "reload preserves selection",
            "accent-insensitive search and keyboard",
            "exact Marcio contact",
            "missing Leticia contact",
            "unknown instructor and educational contacts",
            "subject switch escapes selection",
            "no repeated confirmation",
            "cancel and resume",
            "ambiguous document clarification",
            "real PDF RAG sources",
            "desktop/mobile fixed composer",
          ],
          consoleErrors: errors,
        },
        null,
        2,
      ),
    );
  } finally {
    await browser.close();
  }
}
run().catch((e) => {
  console.error(e);
  process.exit(1);
});
