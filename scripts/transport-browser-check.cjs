const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs");
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
    page.on("pageerror", (error) => errors.push(String(error)));
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
      name: "Segunda via de vale-transporte",
    });
    const search = flow.getByRole("searchbox", {
      name: "Buscar cartão ou operadora",
    });
    async function settled() {
      await page.waitForFunction(
        () => !document.querySelector("#message").disabled,
        null,
        { timeout: 180000 },
      );
    }
    async function send(text) {
      const response = page.waitForResponse(
        (r) => r.url().endsWith("/stream") && r.status() === 200,
        { timeout: 180000 },
      );
      await field.fill(text);
      await field.press("Enter");
      await response;
      await settled();
    }
    async function choose(name) {
      const response = page.waitForResponse(
        (r) => r.url().endsWith("/stream") && r.status() === 200,
        { timeout: 180000 },
      );
      await flow.getByRole("button", { name, exact: false }).click();
      await response;
      await settled();
    }
    await send("Perdi meu vale-transporte.");
    await search.waitFor();
    await flow.getByRole("button", { name: /SPTRANS/ }).waitFor();
    assert.equal(await flow.getByRole("listitem").count(), 33);
    assert.ok(!(await flow.innerText()).includes("Procedimento"));
    assert.ok(!(await flow.innerText()).includes("7 tarifas"));
    await page.reload();
    await search.waitFor();
    await search.fill("sptrans");
    assert.equal(await flow.getByRole("listitem").count(), 1);
    await search.press("Tab");
    assert.ok(
      (await page.evaluate(() => document.activeElement.textContent)).includes(
        "SPTRANS",
      ),
    );
    await choose(/SPTRANS/);
    let last = page.locator("article").last();
    assert.ok((await last.innerText()).includes("7 tarifas"));
    assert.ok((await last.innerText()).includes("72 horas"));
    await last.getByText(/Fontes consultadas/).click();
    await last.getByText(/Código do benefício: 89/).waitFor();
    await send("E quanto custa?");
    last = page.locator("article").last();
    assert.ok((await last.innerText()).includes("7 tarifas"));
    assert.ok(!(await last.innerText()).includes("R$ 28,50"));
    await choose("Trocar cartão de transporte");
    await search.fill("top");
    await choose(/^TOP/);
    assert.ok(
      (await page.locator("article").last().innerText()).includes("R$ 28,50"),
    );
    await choose("Trocar cartão de transporte");
    await search.fill("diadema");
    await choose(/SOU Diadema/);
    assert.equal(
      await page
        .locator("article")
        .last()
        .getByRole("link", { name: "sac@soudiadema.com.br", exact: true })
        .getAttribute("href"),
      "mailto:sac@soudiadema.com.br",
    );
    await choose("Trocar cartão de transporte");
    await search.fill("guarulhos");
    await choose(/Guarupas/);
    assert.ok(
      (await page.locator("article").last().innerText()).includes(
        "solicitação cabe à empresa",
      ),
    );
    await send("Meu cartão é Inexistente.");
    await search.waitFor();
    await search.fill("zzzz");
    assert.equal(await flow.getByRole("listitem").count(), 0);
    await search.fill("");
    fs.mkdirSync("tmp/transport-qa", { recursive: true });
    for (const [width, height] of [
      [1440, 900],
      [1366, 768],
      [390, 844],
      [390, 400],
    ]) {
      await page.setViewportSize({ width, height });
      await page.waitForTimeout(100);
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
        path: `tmp/transport-qa/cards-${width}-${height}.png`,
      });
    }
    await page.setViewportSize({ width: 390, height: 844 });
    await search.fill("sptrans");
    await choose(/SPTRANS/);
    await flow
      .getByRole("button", { name: "Trocar cartão de transporte", exact: true })
      .waitFor();
    await page.screenshot({ path: "tmp/transport-qa/sptrans-mobile.png" });
    await send("Onde baixo meu holerite?");
    await search.waitFor({ state: "hidden" });
    assert.ok(
      (await page.locator("article").last().innerText()).includes(
        "Conecta Jovem",
      ),
    );
    assert.deepEqual(errors, []);
    console.log(
      JSON.stringify(
        {
          result: "PASS",
          checks: [
            "33 names without procedures",
            "reload and search",
            "keyboard selection",
            "SPTrans and 7 tariffs/72h",
            "exact card followup",
            "TOP separate currency rate",
            "Diadema clickable email",
            "Guarulhos company responsibility",
            "unknown card and no search results",
            "switch card",
            "four responsive viewports",
            "fixed composer",
            "subject change preserves Conecta flow",
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
run().catch((error) => {
  console.error(error);
  process.exit(1);
});
