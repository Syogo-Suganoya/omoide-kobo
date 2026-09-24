/**
 * クリップボードへのコピー。
 *
 * `navigator.clipboard` は安全なコンテキスト（https か localhost）でしか生えないので、
 * スマホから LAN の IP で開いた画面では丸ごと undefined になる。
 * 共有リンクを渡すのはまさにその場面なので、古い execCommand を控えに置く。
 * それも駄目なときは false を返し、呼び出し側が URL を見せて手で選べるようにする。
 */
export async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // 権限が下りなかった場合。下の控えに進む
  }

  try {
    const area = document.createElement("textarea");
    area.value = text;
    // 画面外に置く。iOS は readOnly だとキーボードが出ないので合わせて指定する
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.top = "-1000px";
    document.body.appendChild(area);
    area.select();
    area.setSelectionRange(0, text.length);
    const ok = document.execCommand("copy");
    document.body.removeChild(area);
    return ok;
  } catch {
    return false;
  }
}
