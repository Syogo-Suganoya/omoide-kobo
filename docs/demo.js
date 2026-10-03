/**
 * 提出用のデモ動画を撮る。
 *
 *   docker compose --profile shots run --rm demo
 *
 * 入口から共有まで、利用者と同じ順に画面を操作して1本の動画にする。
 * 見る人が目で追えるように、カーソルを描いて動かし、文字はゆっくり打ち、
 * 段ごとに下へ字幕を出す。長さは気にせず、操作の流れが分かることを優先する。
 *
 * 写真は docs/demo/photos/ に置いた JPEG/PNG を使う（無ければ canvas で描いた白黒写真）。
 * docs/demo/ は gitignore 済みなので、家族の写真を置いてもリポジトリには入らない。
 *
 * 入口の「はじめまして」から撮るため、まっさらなブラウザで家族を新しく作る。
 * 撮った家族は残るので、開発のエミュレータだけを相手にすること。
 */

const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const puppeteer = require("puppeteer");

const WEB = process.env.WEB_URL || "http://omoide-kobo.local:5173";
const API = process.env.API_URL || "/api";
const OUT = process.env.OUT_DIR || "/work/docs/demo";
const PHOTOS = process.env.PHOTO_DIR || path.join(OUT, "photos");

// 16:9 の 720p で書き出す（screencast は CSS ピクセルの大きさで撮る）。
// 描画だけ 1.5 倍で行い、縮めて書き出すので文字の縁がなめらかになる
const WIDTH = 1280;
const HEIGHT = 720;
const SCALE = 1.5;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** 手元に写真が無いときの代わり。画面の流れを見せるだけなら、これで足りる */
async function drawSamples(page, dir) {
  fs.mkdirSync(dir, { recursive: true });
  const shots = await page.evaluate(() =>
    [0, 1, 2].map((seed) => {
      const c = document.createElement("canvas");
      c.width = 900;
      c.height = 620;
      const g = c.getContext("2d");
      g.fillStyle = "#9c968c";
      g.fillRect(0, 0, 900, 620);
      for (let i = 0; i < 9000; i++) {
        g.fillStyle = `rgba(255,255,255,${Math.random() * 0.06})`;
        g.fillRect(Math.random() * 900, Math.random() * 620, 2, 2);
      }
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
      g.fillStyle = "#cfc9c0";
      g.fillRect(390, 330 + seed * 10, 120, 24);
      g.beginPath();
      g.arc(200, 470, 14, 0, Math.PI * 2);
      g.fill();
      g.fillRect(186, 486, 28, 60);
      return c.toDataURL("image/jpeg", 0.9).split(",")[1];
    })
  );
  return shots.map((b64, i) => {
    const file = path.join(dir, `sample-${i + 1}.jpg`);
    fs.writeFileSync(file, Buffer.from(b64, "base64"));
    return file;
  });
}

/**
 * 画面に重ねる小道具。ヘッドレスのブラウザはカーソルを描かないので、
 * 自前で描いてマウスの動きに追従させる。字幕も同じ仕組みで出す。
 */
const OVERLAY = () => {
  const style = document.createElement("style");
  style.textContent = `
    #demo-cursor { position: fixed; z-index: 99999; width: 22px; height: 22px; margin: -3px 0 0 -3px;
      pointer-events: none; transition: transform .12s ease; }
    #demo-cursor.down { transform: scale(.8); }
    #demo-ripple { position: fixed; z-index: 99998; width: 36px; height: 36px; margin: -18px 0 0 -18px;
      border-radius: 50%; border: 3px solid rgba(212,105,74,.8); pointer-events: none; opacity: 0; }
    #demo-ripple.go { animation: demo-ripple .5s ease-out; }
    @keyframes demo-ripple { from { opacity: 1; transform: scale(.3); } to { opacity: 0; transform: scale(1.4); } }
    #demo-caption { position: fixed; z-index: 99997; left: 50%; bottom: 28px; transform: translateX(-50%);
      max-width: 88%; padding: 12px 26px; border-radius: 6px; background: rgba(61,51,42,.9); color: #fffdf7;
      font: 500 20px/1.5 "Kiwi Maru", "Noto Sans CJK JP", sans-serif; letter-spacing: .06em;
      box-shadow: 0 4px 18px rgba(0,0,0,.18); opacity: 0; transition: opacity .35s ease; pointer-events: none; }
    #demo-caption.on { opacity: 1; }
    #demo-caption b { color: #f2b79f; margin-right: .6em; }`;
  const mount = () => {
    if (document.getElementById("demo-cursor")) return;
    document.head.appendChild(style);
    const cursor = document.createElement("div");
    cursor.id = "demo-cursor";
    cursor.innerHTML =
      '<svg viewBox="0 0 24 24" width="22" height="22"><path d="M3 2l7 19 2.6-7.4L20 11z" ' +
      'fill="#fffdf7" stroke="#3d332a" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    const ripple = document.createElement("div");
    ripple.id = "demo-ripple";
    const caption = document.createElement("div");
    caption.id = "demo-caption";
    document.body.append(cursor, ripple, caption);
    const at = JSON.parse(sessionStorage.getItem("demo-cursor") || "[640,360]");
    cursor.style.left = `${at[0]}px`;
    cursor.style.top = `${at[1]}px`;
    document.addEventListener("mousemove", (e) => {
      cursor.style.left = `${e.clientX}px`;
      cursor.style.top = `${e.clientY}px`;
      sessionStorage.setItem("demo-cursor", JSON.stringify([e.clientX, e.clientY]));
    });
    document.addEventListener("mousedown", (e) => {
      cursor.classList.add("down");
      ripple.style.left = `${e.clientX}px`;
      ripple.style.top = `${e.clientY}px`;
      ripple.classList.remove("go");
      void ripple.offsetWidth;
      ripple.classList.add("go");
    });
    document.addEventListener("mouseup", () => cursor.classList.remove("down"));
    // 画面を移っても字幕を引き継ぐ
    const saved = sessionStorage.getItem("demo-caption");
    if (saved) {
      caption.innerHTML = saved;
      caption.classList.add("on");
    }
  };
  if (document.body) mount();
  else document.addEventListener("DOMContentLoaded", mount);
};

async function main() {
  fs.mkdirSync(OUT, { recursive: true });
  const origin = new URL(WEB).origin;
  const browser = await puppeteer.launch({
    executablePath: process.env.CHROME_BIN || "/usr/bin/chromium-browser",
    args: [
      "--no-sandbox",
      "--disable-dev-shm-usage",
      "--font-render-hinting=none",
      // http の開発サーバーを https の本番と同じ扱いにする。
      // こうしないとクリップボードの API がそもそも生えず、コピーが「できません」と映る
      `--unsafely-treat-insecure-origin-as-secure=${origin}`,
    ],
  });
  const context = browser.defaultBrowserContext();
  await context
    .overridePermissions(origin, ["clipboard-read", "clipboard-sanitized-write"])
    .catch((e) => console.log(`クリップボードの権限を付けられませんでした（コピーは代わりの表示になります）: ${e.message}`));

  const page = await browser.newPage();
  await page.setViewport({ width: WIDTH, height: HEIGHT, deviceScaleFactor: SCALE });
  await page.evaluateOnNewDocument(OVERLAY);
  page.on("pageerror", (e) => console.log(`[画面] ${e.message}`));

  // ── 操作の道具 ─────────────────────────────────────────────────
  let mouse = [WIDTH / 2, HEIGHT / 2];

  /** カーソルを目で追える速さで動かす */
  const glide = async (x, y) => {
    const [x0, y0] = mouse;
    const dist = Math.hypot(x - x0, y - y0);
    const steps = Math.max(12, Math.min(40, Math.round(dist / 18)));
    for (let i = 1; i <= steps; i++) {
      const t = i / steps;
      const e = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2; // ease-in-out
      await page.mouse.move(x0 + (x - x0) * e, y0 + (y - y0) * e);
      await sleep(12);
    }
    mouse = [x, y];
  };

  /** 要素を画面に入れてから、カーソルを運んで押す */
  const press = async (handle, { pause = 700 } = {}) => {
    await handle.evaluate((el) => el.scrollIntoView({ block: "center", behavior: "smooth" }));
    await sleep(600);
    const box = await handle.boundingBox();
    if (!box) throw new Error("押す先が画面に出ていません");
    await glide(box.x + box.width / 2, box.y + box.height / 2);
    await sleep(250);
    await page.mouse.down();
    await sleep(90);
    await page.mouse.up();
    await sleep(pause);
  };

  /** 見えている文言でボタンやリンクを探して押す */
  const pressText = async (text, opts) => {
    const handle = await page.evaluateHandle((t) => {
      const want = t.replace(/\s+/g, "");
      return (
        [...document.querySelectorAll("button, a, summary, label")].find(
          (e) => !e.disabled && e.offsetParent !== null && e.innerText.replace(/\s+/g, "").includes(want)
        ) || null
      );
    }, text);
    const el = handle.asElement();
    if (!el) {
      const seen = await page.evaluate(() => document.body.innerText.slice(0, 300));
      throw new Error(`「${text}」が押せなかった。画面にはこれが出ていた:\n${seen}`);
    }
    await press(el, opts);
  };

  /** 入力欄に、人が打つ速さで書く */
  const typeInto = async (handle, text) => {
    await press(handle, { pause: 200 });
    await handle.type(text, { delay: 55 });
    await sleep(400);
  };

  const caption = async (step, text) => {
    const html = step ? `<b>${step}</b>${text}` : text;
    await page.evaluate((h) => {
      sessionStorage.setItem("demo-caption", h);
      const c = document.getElementById("demo-caption");
      if (!c) return;
      c.classList.remove("on");
      setTimeout(() => {
        c.innerHTML = h;
        c.classList.add("on");
      }, 250);
    }, html);
    await sleep(1400);
  };

  const waitForHeading = async (text, timeout = 60000) => {
    try {
      await page.waitForFunction(
        (t) => [...document.querySelectorAll("h1, h2, h3")].some((h) => h.textContent.includes(t)),
        { timeout },
        text
      );
    } catch {
      const seen = await page.evaluate(() => document.body.innerText.slice(0, 300));
      throw new Error(`「${text}」が出なかった。画面にはこれが出ていた:\n${seen}`);
    }
    await sleep(500);
  };

  /** ページをゆっくり送って見せる */
  const tour = async (to, ms = 2200) => {
    await page.evaluate((y) => window.scrollTo({ top: y, behavior: "smooth" }), to);
    await sleep(ms);
  };

  const api = (pathname, init) =>
    page.evaluate(
      async (base, p, i) => {
        const r = await fetch(base + p, i);
        return r.json();
      },
      API,
      pathname,
      init
    );

  // ── 準備（録画の外） ─────────────────────────────────────────
  await page.goto(`${WEB}/`, { waitUntil: "networkidle0" });
  const modes = (await api("/agents")).modes;
  console.log(`推定: ${modes.gemini} / 経路: ${modes.ekispert}`);
  if (modes.gemini === "mock") {
    console.log(
      "\n⚠ GEMINI_MODE=mock で撮っています。推定の中身はモックの作り話です。\n" +
        "  提出する動画に使うなら、live で撮り直すか、モックであることを明記してください。\n"
    );
  }

  let photos = fs.existsSync(PHOTOS)
    ? fs
        .readdirSync(PHOTOS)
        .filter((f) => /\.(jpe?g|png)$/i.test(f))
        .sort()
        .map((f) => path.join(PHOTOS, f))
    : [];
  if (photos.length === 0) {
    console.log(`${PHOTOS} に写真が無いので、描いた白黒写真を使います`);
    photos = await drawSamples(page, "/tmp/demo-samples");
  }
  photos = photos.slice(0, 3);
  console.log(`写真 ${photos.length} 枚: ${photos.map((p) => path.basename(p)).join(", ")}`);

  // 家族はブラウザごとに覚えているだけなので、忘れさせれば「はじめまして」から撮れる
  await page.evaluate(() => {
    localStorage.clear();
    sessionStorage.clear();
  });
  // 案内ページは撮らない。「写真を調べる」を押した先の、わが家から始める
  await page.goto(`${WEB}/home`, { waitUntil: "networkidle0" });
  await page.evaluate(() => document.fonts.ready);
  await sleep(800);

  // ── 録画 ─────────────────────────────────────────────────────
  const webm = path.join(OUT, "demo.webm");
  const recorder = await page.screencast({ path: webm });
  console.log("録画を始めました");

  // 1. はじめる
  await caption("①", "はじめる ― 入力は要りません。ボタンひとつで写真を入れる画面まで");
  await waitForHeading("はじめまして");
  await sleep(1800);
  await pressText("写真を入れる", { pause: 400 });
  await waitForHeading("実家のアルバム");
  await sleep(1000);

  // 2. 写真を入れる
  await caption("②", "写真を入れる ― アルバムのページをスマホで撮って、まとめて放り込むだけ");
  const drop = await page.$(".dropzone");
  const dropBox = await drop.boundingBox();
  await glide(dropBox.x + dropBox.width / 2, dropBox.y + dropBox.height / 2);
  await sleep(500);
  await (await page.$('input[type="file"]')).uploadFile(...photos);

  // 3. 推定を待つ
  await caption("③", "推定 ― 駅舎・看板・服装を手がかりに、撮影地と年代の候補を出します");
  await waitForHeading("いま調べています");
  await page.evaluate(() =>
    [...document.querySelectorAll("h2")].find((h) => h.innerText.includes("いま調べています"))
      ?.scrollIntoView({ block: "start", behavior: "smooth" })
  );

  // 失敗した写真は、推定し直してから先へ進む（無料枠の 429 で1枚落ちることがある）
  const family = { id: await page.evaluate(() => localStorage.getItem("omoide.familyId")) };
  let settled = false;
  for (let i = 0; i < 180 && !settled; i++) {
    const list = await api(`/families/${family.id}/photos`);
    settled = list.length === photos.length && list.every((p) => ["awaiting_family", "failed"].includes(p.status));
    if (!settled) await sleep(1000);
  }
  for (let round = 0; round < 3; round++) {
    const failed = (await api(`/families/${family.id}/photos`)).filter((p) => p.status === "failed");
    if (failed.length === 0) break;
    console.log(`推定に失敗した写真が${failed.length}枚。やり直します（${round + 1}回目）`);
    for (const p of failed) {
      await sleep(4000);
      await api(`/photos/${p.id}/reestimate`, { method: "POST" }).catch(() => null);
    }
  }
  const stillFailed = (await api(`/families/${family.id}/photos`)).filter((p) => p.status === "failed");
  if (stillFailed.length) console.log(`⚠ ${stillFailed.length}枚は失敗のまま映ります: ${stillFailed[0].error}`);
  await sleep(2500);
  await page.reload({ waitUntil: "networkidle0" });
  await sleep(800);
  await page.evaluate(() =>
    [...document.querySelectorAll("h2")].find((h) => h.innerText === "写真")?.scrollIntoView({ block: "start", behavior: "smooth" })
  );
  await sleep(2400);

  // 4. 確かめて確定する
  await caption("④", "確かめる ― 候補には根拠と確度。AIは候補までを出します。");
  await pressText("場所を確かめる");
  await waitForHeading("家族にたずねる");
  await sleep(1200);
  // AI の推定（左の列）を見せる
  await page.evaluate(() =>
    [...document.querySelectorAll("h3")].find((h) => h.innerText.includes("AI の推定"))
      ?.scrollIntoView({ block: "start", behavior: "smooth" })
  );
  await sleep(3200);
  await pressText("場所を決める", { pause: 1200 });

  const answers = ["母の実家の最寄り駅です", "叔母を見送った日だと思います", "乾物屋さんのテントでした"];
  const inputs = await page.$$("details.fold .field input");
  for (let i = 0; i < Math.min(answers.length, inputs.length - 3); i++) {
    await typeInto(inputs[i], answers[i]);
  }
  await pressText("」を入れる", { pause: 900 }); // 場所の候補
  await pressText("家族の記憶として確定する", { pause: 1800 });
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" }));
  await sleep(2600);

  // 残りの写真も確定しておく（旅程には2か所以上あると見栄えがよい）
  await caption("", "1枚ずつ確かめていきます");
  for (let i = 1; i < photos.length; i++) {
    const next = await page.evaluateHandle(() =>
      [...document.querySelectorAll("a")].find((a) => a.innerText.includes("次の写真へ")) || null
    );
    if (!next.asElement()) break;
    await press(next.asElement(), { pause: 400 });
    await waitForHeading("家族にたずねる");
    await sleep(900);
    await pressText("」を入れる", { pause: 600 });
    await pressText("家族の記憶として確定する", { pause: 1500 });
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" }));
    await sleep(1200);
  }

  // 5. 旅程を組む
  await caption("⑤", "旅をつくる ― 確定した場所を選び、親の体力に合わせて一日を組みます");
  await pressText("旅をつくる");
  await waitForHeading("思い出の場所を選ぶ");
  await sleep(900);
  for (const card of await page.$$(".polaroid")) await press(card, { pause: 500 });
  const day = new Date(Date.now() + 21 * 864e5).toISOString().slice(0, 10);
  const date = await page.$('input[type="date"]');
  await press(date, { pause: 300 });
  await date.evaluate((el, v) => {
    Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set.call(el, v);
    el.dispatchEvent(new Event("input", { bubbles: true }));
  }, day);
  await sleep(800);
  await pressText("旅程をつくる", { pause: 600 });
  await caption("⑤", "現存か・建替えか・廃止かを確かめ、休憩と昼食を挟んだ旅程にします");
  await waitForHeading("訪ねる場所の現況", 120000);
  await sleep(600);
  await page.evaluate(() =>
    [...document.querySelectorAll("h2")].find((h) => h.innerText.includes("巡礼"))
      ?.scrollIntoView({ block: "start", behavior: "smooth" })
  );
  await sleep(3000);
  const tripTop = await page.evaluate(() => window.scrollY);
  for (let y = tripTop + 380; y < tripTop + 2400; y += 380) await tour(y, 1500);
  await sleep(1200);

  // 6. 共有する
  await caption("⑥", "家族に見せる ― 期限つきのリンクを作って、いつもの連絡手段で渡します");
  await pressText("家族に見せる");
  await waitForHeading("共有リンク");
  await sleep(900);
  await pressText("リンクを作る", { pause: 1400 });
  await pressText("コピー", { pause: 1600 });

  // 受け取った側の見え方
  await caption("⑥", "受け取った家族には、確定した場所と写真だけが見えます");
  const link = await page.$eval(".linkbox input", (el) => el.value);
  await page.goto(link, { waitUntil: "networkidle0" });
  await sleep(3500);
  await tour(420, 2400);

  await caption("", "オモイデ工房 ― 確定するのは、いつも家族");
  await sleep(3000);

  await recorder.stop();
  await browser.close();
  console.log(`録画: ${webm}`);

  // 提出先によっては webm を受け付けないので、mp4 も作る
  const mp4 = path.join(OUT, "demo.mp4");
  try {
    execFileSync(
      "ffmpeg",
      ["-y", "-loglevel", "error", "-i", webm, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
        "-movflags", "+faststart", mp4],
      { stdio: "inherit" }
    );
    console.log(`変換: ${mp4}`);
  } catch (e) {
    console.log(`mp4 への変換に失敗しました（webm はそのまま使えます）: ${e.message}`);
  }
}

main().catch((err) => {
  console.error(err.message);
  process.exit(1);
});
