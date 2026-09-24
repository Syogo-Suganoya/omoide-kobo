/**
 * 案内ページ「使い方」に載せる画面の写しを撮る。
 *
 *   docker compose --profile shots up --build shots
 *
 * 利用者と同じ順に操作して撮るので、画面を変えたら撮り直すだけで追随する。
 * 撮る順・ファイル名は LandingPage.tsx の STEPS と対で、片方を変えたらもう片方も直すこと。
 *
 * **この本は家族のデータを消す。** 1枚目は「家族がまだ無い人の入口」なので、
 * 撮る前に家族を全部消す。開発のエミュレータ（メモリ上）だけを相手にすること。
 */

const fs = require("fs");
const path = require("path");
const puppeteer = require("puppeteer");

const WEB = process.env.WEB_URL || "http://web:5173";
// 画面と同じ入口（web の /api プロキシ）を通す。別 origin を直に叩くと CORS で弾かれる。
const API = process.env.API_URL || "/api";
const OUT = process.env.OUT_DIR || "/work/frontend/public/guide";
const TMP = "/tmp/shots";

// 案内ページの図と同じ横幅で撮る。deviceScaleFactor 2 で文字が潰れない。
const WIDTH = 1120;
const HEIGHT = 860;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** 祖父母のアルバムに見える白黒写真を、ブラウザの canvas で作る（素材を持ち込まないため） */
async function makeSamples(page) {
  fs.mkdirSync(TMP, { recursive: true });
  const shots = await page.evaluate(() => {
    const draw = (seed) => {
      const c = document.createElement("canvas");
      c.width = 900;
      c.height = 620;
      const g = c.getContext("2d");
      g.fillStyle = "#9c968c";
      g.fillRect(0, 0, c.width, c.height);
      // 空の粒状感
      for (let i = 0; i < 9000; i++) {
        g.fillStyle = `rgba(255,255,255,${Math.random() * 0.06})`;
        g.fillRect(Math.random() * c.width, Math.random() * c.height, 2, 2);
      }
      // 山なみ
      g.fillStyle = "#6f6859";
      g.beginPath();
      g.moveTo(0, 430 + seed * 18);
      g.lineTo(250 + seed * 40, 250);
      g.lineTo(470, 400);
      g.lineTo(700 - seed * 30, 300);
      g.lineTo(900, 420);
      g.lineTo(900, 620);
      g.lineTo(0, 620);
      g.closePath();
      g.fill();
      // 駅舎
      g.fillStyle = "#8b857c";
      g.fillRect(300, 360 + seed * 10, 300, 150);
      g.fillStyle = "#5e584e";
      g.beginPath();
      g.moveTo(280, 360 + seed * 10);
      g.lineTo(620, 360 + seed * 10);
      g.lineTo(560, 300 + seed * 10);
      g.lineTo(340, 300 + seed * 10);
      g.closePath();
      g.fill();
      // 看板
      g.fillStyle = "#cfc9c0";
      g.fillRect(390, 330 + seed * 10, 120, 24);
      // 人影
      g.fillStyle = "#cfc9c0";
      g.beginPath();
      g.arc(200, 470, 14, 0, Math.PI * 2);
      g.fill();
      g.fillRect(186, 486, 28, 60);
      // 焼きつきのむら
      const v = g.createRadialGradient(450, 310, 120, 450, 310, 520);
      v.addColorStop(0, "rgba(0,0,0,0)");
      v.addColorStop(1, "rgba(40,30,20,0.35)");
      g.fillStyle = v;
      g.fillRect(0, 0, c.width, c.height);
      return c.toDataURL("image/jpeg", 0.9).split(",")[1];
    };
    return [0, 1, 2].map(draw);
  });

  return shots.map((b64, i) => {
    const file = path.join(TMP, `omoide-${i + 1}.jpg`);
    fs.writeFileSync(file, Buffer.from(b64, "base64"));
    return file;
  });
}

async function main() {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await puppeteer.launch({
    executablePath: process.env.CHROME_BIN || "/usr/bin/chromium-browser",
    args: ["--no-sandbox", "--disable-dev-shm-usage", "--font-render-hinting=none"],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: WIDTH, height: HEIGHT, deviceScaleFactor: 2 });
  page.on("pageerror", (e) => console.log(`[画面] ${e.message}`));
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`[画面] ${m.text()}`);
  });
  page.on("requestfailed", (r) => console.log(`[取得できず] ${r.url()} (${r.failure()?.errorText})`));
  page.on("response", (r) => {
    if (r.status() >= 400) console.log(`[${r.status()}] ${r.url()}`);
  });

  /**
   * 見出し `from` の頭から、`to` の裾までが収まる高さで1枚撮る。
   *
   * 案内ページ側の枠（`.guide .shot`）は 16:10 に固定してあり、入りきらない分は下が切れる。
   * ここで頭出しを合わせておけば、切れても大事なところは残る。
   * 上のメニューは貼りついたまま動かないので、その分だけ下げて頭出しする
   * （素直に scrollIntoView するとメニューの裏に隠れる）。
   */
  const frame = async (name, { from, to, pad = 28, max = 2400 } = {}) => {
    // 進行ログのように、測ったそばから伸びる画面がある。落ち着いてから測る。
    await page
      .waitForFunction(
        () => {
          const h = document.body.scrollHeight;
          if (window.__lastH === h) return true;
          window.__lastH = h;
          return false;
        },
        { polling: 400, timeout: 15000 }
      )
      .catch(() => {});
    await page.evaluate(() => delete window.__lastH);

    const box = await page.evaluate(
      (fromText, toText) => {
        const find = (t) =>
          t &&
          [...document.querySelectorAll("h2, h3, section, .card, .now-bar, .block")].find((e) =>
            e.innerText?.includes(t)
          );
        const bar = document.querySelector(".topbar")?.getBoundingClientRect().height ?? 0;
        const head = find(fromText);
        const tail = find(toText) ?? head;
        if (!head) return null;
        const top = head.getBoundingClientRect().top + window.scrollY;
        const bottom = tail.getBoundingClientRect().bottom + window.scrollY;
        return { bar, top, bottom };
      },
      from,
      to
    );
    if (!box) throw new Error(`「${from}」が見つからないので ${name} を撮れません`);

    const height = Math.round(Math.min(max, box.bottom - box.top + box.bar + pad * 2));
    await page.setViewport({ width: WIDTH, height, deviceScaleFactor: 2 });
    await sleep(300);
    await page.evaluate((y) => window.scrollTo(0, y), Math.max(0, box.top - box.bar - pad));
    // 字が載りきる前に撮ると別物になる
    await page.evaluate(() => document.fonts.ready).catch(() => {});
    await sleep(500);
    await page.screenshot({ path: `${OUT}/${name}.png` });
    console.log(`撮影: ${name}.png`);
  };

  /** 見出しで画面の切り替わりを待つ。出なければ、何が出ていたのかを添えて落とす。 */
  const waitForHeading = async (text) => {
    try {
      await page.waitForFunction(
        (t) => [...document.querySelectorAll("h2, h3")].some((h) => h.textContent.includes(t)),
        { timeout: 30000 },
        text
      );
    } catch {
      const seen = await page.evaluate(() => document.body.innerText.slice(0, 300));
      throw new Error(`「${text}」が出なかった。画面にはこれが出ていた:\n${seen}`);
    }
    await sleep(600);
  };

  const clickText = async (text) => {
    const ok = await page.evaluate((t) => {
      const el = [...document.querySelectorAll("button, a")].find((e) =>
        e.innerText.replace(/\s+/g, "").includes(t.replace(/\s+/g, ""))
      );
      if (!el) return false;
      el.click();
      return true;
    }, text);
    if (!ok) {
      const seen = await page.evaluate(() => document.body.innerText.slice(0, 300));
      throw new Error(`「${text}」が押せなかった。画面にはこれが出ていた:\n${seen}`);
    }
    await sleep(700);
  };

  // React の input は値を直に入れても気づかない。ネイティブの setter を通す。
  const fill = async (selector, value) => {
    await page.waitForSelector(selector, { timeout: 20000 });
    await page.evaluate(
      (sel, val) => {
        const el = document.querySelector(sel);
        const setter = Object.getOwnPropertyDescriptor(
          window.HTMLInputElement.prototype,
          "value"
        ).set;
        setter.call(el, val);
        el.dispatchEvent(new Event("input", { bubbles: true }));
      },
      selector,
      value
    );
    await sleep(300);
  };

  await page.goto(`${WEB}/`, { waitUntil: "networkidle0" });
  const samples = await makeSamples(page);

  // 1枚目は「家族がまだ無い人の入口」。先に消しておく。
  const wiped = await page.evaluate(async (api) => {
    const families = await (await fetch(`${api}/families`)).json();
    for (const f of families) await fetch(`${api}/families/${f.id}`, { method: "DELETE" });
    return families.length;
  }, API);
  console.log(`家族を${wiped}件消して、入口から撮り直します`);

  // ── 01 はじめる ───────────────────────────────────────────────
  await page.goto(`${WEB}/home`, { waitUntil: "networkidle0" });
  await waitForHeading("はじめまして");
  await frame("01-family", { from: "はじめまして", to: "はじめまして" });

  // ── 02 写真を入れる ──────────────────────────────────────────
  await clickText("写真を入れる");
  await waitForHeading("実家のアルバム");
  await frame("02-upload", { from: "実家のアルバム", to: "上の枠に写真を入れると" });

  // ── 03 推定が終わるのを待つ ─────────────────────────────────
  const input = await page.$('input[type="file"]');
  await input.uploadFile(...samples);
  await waitForHeading("いま調べています");
  await frame("03-progress", { from: "いま調べています", to: "いま調べています" });

  // ── 04 質問に答えて、場所を確定する ─────────────────────────
  // 推定の終わりは API で見る。1枚でも失敗したら、その理由を添えて止める
  // （鍵なしのイメージで live を指したときに、無言で時間切れにならないように）。
  const done = await page.evaluate(async (api) => {
    const family = (await (await fetch(`${api}/families`)).json())[0];
    for (let i = 0; i < 120; i++) {
      const photos = await (await fetch(`${api}/families/${family.id}/photos`)).json();
      const failed = photos.find((p) => p.status === "failed");
      if (failed) return { error: failed.error };
      if (photos.length > 0 && photos.every((p) => p.status === "awaiting_family")) return { ok: true };
      await new Promise((r) => setTimeout(r, 1000));
    }
    return { error: "推定が終わりませんでした（2分）" };
  }, API);
  if (!done.ok) {
    throw new Error(
      `推定が通らないので、この先は撮れません: ${done.error}\n` +
        "モックで撮るのが確実です: GEMINI_MODE=mock EKISPERT_MODE=mock docker compose up -d api"
    );
  }
  await page.reload({ waitUntil: "networkidle0" });
  await sleep(800);
  const photoHref = await page.evaluate(() => document.querySelector(".polaroid").getAttribute("href"));
  await page.goto(`${WEB}${photoHref}`, { waitUntil: "networkidle0" });
  await waitForHeading("家族にたずねる");
  // 説明文が「質問に答えて、場所を確定する」なので、答えが入った状態を見せる
  await page.evaluate(() => {
    const el = [...document.querySelectorAll("details.fold")].find((d) =>
      d.innerText.includes("家族にたずねる")
    );
    if (el) el.open = true;
  });
  const answers = [
    "母の実家の最寄り駅です。名前は覚えていません",
    "叔母を見送った日だと思います",
    "このテントは乾物屋さんのものでした",
  ];
  const boxes = await page.$$("details.fold .field input");
  for (let i = 0; i < Math.min(answers.length, boxes.length); i++) {
    await boxes[i].type(answers[i], { delay: 4 });
  }
  await clickText("」を入れる"); // 場所の候補を入れる
  await sleep(400);
  await frame("04-confirm", { from: "家族にたずねる", to: "家族の記憶として確定する" });

  // ── 05 巡礼の旅程を組む ─────────────────────────────────────
  // 旅程には確定した場所が要る。写真を2枚確定しておく。
  await clickText("家族の記憶として確定する");
  await sleep(1500);
  await page.goto(`${WEB}${photoHref}`, { waitUntil: "networkidle0" });
  await clickText("次の写真へ");
  await waitForHeading("家族にたずねる");
  await clickText("」を入れる");
  await sleep(300);
  await clickText("家族の記憶として確定する");
  await sleep(1500);

  await page.goto(`${WEB}/trip`, { waitUntil: "networkidle0" });
  await waitForHeading("思い出の場所を選ぶ");
  await page.evaluate(() => document.querySelectorAll(".polaroid").forEach((p) => p.click()));
  await sleep(400);
  const day = new Date(Date.now() + 21 * 864e5).toISOString().slice(0, 10);
  await fill('input[type="date"]', day);
  await clickText("旅程をつくる");
  await waitForHeading("訪ねる場所の現況");
  await sleep(600);
  // 旅程は長い。全部入れると細長くなるので、休憩と昼食が挟まったあたりで切る。
  await frame("05-trip", { from: "思い出巡礼旅", to: "体力・バリアフリーの配慮", max: 1200 });

  // ── 06 家族に共有する ───────────────────────────────────────
  await page.goto(`${WEB}/share`, { waitUntil: "networkidle0" });
  await waitForHeading("共有リンク");
  await clickText("リンクを作る");
  await sleep(1400);
  await frame("06-share", { from: "共有リンク", to: "共有を止める" });

  await browser.close();
  console.log(`\n${OUT} に6枚。案内ページを開いて確かめてください。`);
}

main().catch((err) => {
  console.error(err.message);
  process.exit(1);
});
