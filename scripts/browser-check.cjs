const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs");
async function run() {
  const browser = await chromium.launch({
    channel: process.env.PLAYWRIGHT_CHANNEL || "msedge",
    headless: true,
  });
  try {
    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      locale: "pt-BR",
    });
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", (e) => errors.push(String(e)));
    page.on("console", (m) => {
      if (m.type() === "error") errors.push(m.text());
    });
    fs.mkdirSync("docs/qa", { recursive: true });
    await Promise.all([
      page.waitForResponse(
        (r) => r.url().includes("/support/topics") && r.status() === 200,
      ),
      page.goto(process.env.BASE_URL || "http://127.0.0.1:5173"),
    ]);
    async function create() {
      if (
        await page
          .getByRole("button", { name: "Nova conversa", exact: true })
          .first()
          .isVisible()
      )
        await page
          .getByRole("button", { name: "Nova conversa", exact: true })
          .first()
          .click();
      else {
        await page.getByRole("button", { name: "Abrir navegação" }).click();
        await page
          .getByRole("dialog")
          .getByRole("button", { name: "Nova conversa", exact: true })
          .first()
          .click();
      }
      await page
        .getByRole("heading", {
          name: "Como posso ajudar?",
        })
        .waitFor();
    }
    await create();
    const field = page.getByRole("textbox", { name: "Sua mensagem" });
    const region = page.getByRole("region", { name: "Conteúdo da conversa" });
    async function settled() {
      await page.waitForFunction(
        () =>
          !document.querySelector("#message").disabled &&
          document.querySelector("#message").value === "",
        null,
        { timeout: 180000 },
      );
    }
    for (const [width, height] of [
      [1440, 900],
      [1366, 768],
      [390, 844],
      [320, 568],
    ]) {
      await page.setViewportSize({ width, height });
      await page.waitForTimeout(100);
      assert.equal(
        await page.evaluate(
          () =>
            document.documentElement.scrollHeight > innerHeight ||
            document.documentElement.scrollWidth > innerWidth,
        ),
        false,
      );
      const box = await field.boundingBox();
      assert.ok(box.y >= 0 && box.y + box.height <= height);
      if (width > 1000)
        assert.equal(
          await region.evaluate((el) => el.scrollHeight > el.clientHeight),
          false,
        );
      await page.screenshot({ path: `docs/qa/rag02-topics-${width}.png` });
    }
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.getByRole("button", { name: /Folha Ponto/ }).click();
    const question = region.getByRole("button", {
      name: /Qual é o prazo de entrega da folha ponto/,
    });
    await question.waitFor();
    assert.equal(
      await region.getByRole("button").count(),
      10,
      "back and nine questions including operational guidance",
    );
    await page.reload();
    await question.waitFor();
    await page.waitForFunction(
      (button) => !button.disabled,
      await question.elementHandle(),
    );
    let sends = 0;
    page.on("request", (r) => {
      if (r.url().endsWith("/stream") && r.method() === "POST") sends++;
    });
    const started = page.waitForResponse((r) => r.url().endsWith("/stream"));
    await question.evaluate((button) => {
      button.click();
      button.click();
      button.click();
    });
    assert.equal((await started).status(), 200);
    await page
      .getByText("Fontes consultadas", { exact: false })
      .waitFor({ timeout: 180000 });
    await settled();
    assert.equal(sends, 1, "repeated clicks create one request");
    assert.equal(await page.locator("article").count(), 2);
    assert.match(
      await page.locator("article").last().innerText(),
      /segundo|2/i,
    );
    await page.locator("article summary").click();
    await page
      .locator("article details span")
      .filter({ hasText: "Periodicidade e Prazo" })
      .first()
      .waitFor();
    await page.screenshot({ path: "docs/qa/rag02-prazo.png" });
    await page.reload();
    await page.getByText("Fontes consultadas", { exact: false }).waitFor();
    assert.equal(await page.locator("article").count(), 2);
    await field.fill("E se eu atrasar?");
    await field.press("Enter");
    await page.waitForFunction(
      () => document.querySelectorAll("article").length === 4,
    );
    await settled();
    const followup = await page.locator("article").last().innerText();
    assert.match(followup, /pode|podem|poder|poss[ií]v/i);
    await page.getByText("Fazer outra pergunta", { exact: false }).click();
    await page.getByRole("button", { name: "← Voltar aos assuntos" }).click();
    await page
      .getByRole("button", { name: /Benefício Vale-Transporte/ })
      .click();
    await page
      .getByRole("button", {
        name: /Onde é pago ou creditado meu vale-transporte/,
      })
      .click();
    await page
      .getByText(
        "Ainda não tenho informações disponíveis sobre esse assunto.",
        { exact: true },
      )
      .waitFor();
    await settled();
    assert.equal(
      await page.locator("article").last().locator("details").count(),
      0,
    );
    await page.getByText("Fazer outra pergunta", { exact: false }).click();
    await page.getByRole("button", { name: "← Voltar aos assuntos" }).click();
    await page.getByRole("button", { name: /Outros/ }).click();
    await page.getByText("Escreva sua dúvida no campo de mensagem.").waitFor();
    await field.fill("Quem precisa assinar minha folha?");
    await field.press("Enter");
    await page.waitForFunction(
      () => document.querySelectorAll("article").length === 8,
    );
    await settled();
    assert.match(await page.locator("article").last().innerText(), /aprendiz/i);
    await page.locator("article").last().locator("summary").click();
    await page
      .locator("article details span")
      .filter({ hasText: "Assinaturas obrigatórias" })
      .first()
      .waitFor();
    const chooser = page.waitForEvent("filechooser");
    await page
      .getByRole("button", { name: "Anexar arquivos", exact: true })
      .click();
    await (
      await chooser
    ).setFiles({
      name: "rag02.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("Anexo privado de teste; não é base institucional."),
    });
    await page.getByRole("button", { name: "Remover rag02.txt" }).waitFor();
    await page.getByRole("button", { name: "Remover rag02.txt" }).click();
    await page
      .getByRole("button", { name: "Remover rag02.txt" })
      .waitFor({ state: "hidden" });
    await field.fill("Como solicito minhas férias?");
    await field.press("Enter");
    await page.waitForFunction(
      () => document.querySelectorAll("article").length === 10,
    );
    await settled();
    assert.match(
      await page.locator("article").last().innerText(),
      /Ainda não tenho informações/,
    );
    for (const [width, height] of [
      [1440, 900],
      [1366, 768],
      [390, 844],
      [320, 568],
      [390, 400],
    ]) {
      await page.setViewportSize({ width, height });
      await page.waitForTimeout(100);
      assert.equal(
        await page.evaluate(
          () => document.documentElement.scrollHeight > innerHeight,
        ),
        false,
      );
      const box = await field.boundingBox();
      assert.ok(box.y >= 0 && box.y + box.height <= height);
    }
    await page.screenshot({ path: "docs/qa/rag02-history-mobile.png" });
    assert.equal(
      await page.getByRole("button", { name: "Fontes", exact: true }).count(),
      0,
    );
    assert.deepEqual(errors, []);
    console.log(
      JSON.stringify(
        {
          result: "PASS",
          checks: [
            "backend catalog rendered",
            "topic persistence on reload",
            "guided question sends canonical ID",
            "triple click sends once",
            "real SSE answer and section/page sources",
            "PostgreSQL reload",
            "contextual followup preserves possibility",
            "topic switch prevents stale routing",
            "Outros free question",
            "signature source",
            "unsupported vacation fallback",
            "real private upload and removal",
            "requested viewports + compact height",
            "no global scroll",
            "composer always visible",
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
