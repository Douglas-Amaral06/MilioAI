const { chromium } = require("playwright");
const { spawn } = require("node:child_process");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const origin = "http://127.0.0.1:5183";
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
      "5183",
    ],
    { windowsHide: true },
  );
  let output = "";
  server.stdout.on("data", (chunk) => (output += chunk));
  server.stderr.on("data", (chunk) => (output += chunk));
  let browser;
  try {
    for (let i = 0; i < 150 && !output.includes("Local:"); i++) {
      if (server.exitCode !== null) throw new Error(output);
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
    assert.ok(output.includes("Local:"), output);
    browser = await chromium.launch({
      channel: process.env.PLAYWRIGHT_CHANNEL || "msedge",
      headless: true,
    });
    const context = await browser.newContext({ serviceWorkers: "block" });
    await context.route("**/*", (route) =>
      new URL(route.request().url()).origin === origin
        ? route.continue()
        : route.abort(),
    );
    const page = await context.newPage();
    page.setDefaultTimeout(10000);
    await page.goto(origin);
    await page.waitForFunction(
      () =>
        document.querySelector("#message") &&
        !document.querySelector("#message").disabled,
    );
    fs.mkdirSync("tmp/home-qa", { recursive: true });
    const failures = [];
    for (const [width, height] of [
      [1920, 1080],
      [1440, 900],
      [1366, 768],
      [1280, 720],
      [1024, 600],
      [768, 1024],
      [390, 844],
      [375, 667],
      [320, 568],
      [390, 400],
    ]) {
      await page.setViewportSize({ width, height });
      await page.evaluate(
        () =>
          new Promise((resolve) =>
            requestAnimationFrame(() => requestAnimationFrame(resolve)),
          ),
      );
      async function check(label) {
        await page
          .getByRole("heading", { name: "Como posso ajudar?", exact: true })
          .waitFor();
        const state = await page.evaluate(() => {
          const region = document.querySelector(
            '[aria-label="Conteúdo da conversa"]',
          );
          const bounds = region.getBoundingClientRect();
          const visible = (element) => {
            const r = element.getBoundingClientRect();
            return (
              r.width > 0 &&
              r.height > 0 &&
              r.top >= bounds.top - 1 &&
              r.bottom <= bounds.bottom + 1 &&
              r.left >= bounds.left &&
              r.right <= bounds.right + 1
            );
          };
          const welcome = region.querySelector("section");
          const brand = [...welcome.querySelectorAll("i")];
          const controls = [
            ...welcome.querySelectorAll("button, select"),
          ].filter((e) => e.getBoundingClientRect().height > 0);
          return {
            client: region.clientHeight,
            scroll: region.scrollHeight,
            global: document.documentElement.scrollHeight,
            composerBottom: document
              .querySelector("#message")
              .closest("form")
              .getBoundingClientRect().bottom,
            greeting:
              visible(welcome.querySelector("h1")) &&
              visible(welcome.querySelector("h1").previousElementSibling),
            brand: brand.length === 3 && brand.every(visible),
            controls: controls.length > 0 && controls.every(visible),
          };
        });
        await page.locator('[aria-label="Conteúdo da conversa"]').hover();
        await page.mouse.wheel(0, 600);
        const top = await page
          .locator('[aria-label="Conteúdo da conversa"]')
          .evaluate((e) => e.scrollTop);
        if (
          state.scroll > state.client + 1 ||
          state.global > height ||
          state.composerBottom > height ||
          !state.greeting ||
          !state.brand ||
          !state.controls ||
          top !== 0
        )
          failures.push({ width, height, label, ...state, top });
      }
      await check("initial");
      await page.screenshot({
        path: `tmp/home-qa/home-${width}-${height}.png`,
      });
      const topic = page.getByRole("combobox", { name: "Escolher assunto" });
      if (await topic.isVisible())
        await topic.selectOption({ label: "Folha Ponto" });
      else await page.getByRole("button", { name: /Folha Ponto/ }).click();
      await check("selected");
      const question = page.getByRole("combobox", {
        name: "Escolher pergunta",
      });
      if (await question.isVisible()) await question.selectOption("__topics");
      else
        await page
          .getByRole("button", { name: "← Voltar aos assuntos" })
          .click();
    }
    assert.deepEqual(
      failures,
      [],
      "A home deve caber sem rolagem ou composer fora da tela",
    );
    console.log(
      "PASS: home fixa em 10 tamanhos, inicial e assunto selecionado; saudação, marca, controles e composer visíveis; roda do mouse sem rolagem.",
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
