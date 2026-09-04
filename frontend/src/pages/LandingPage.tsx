import { Link } from "react-router-dom";

import { GuideCarousel } from "../components/guide";
import type { GuideStep } from "../components/guide";
import { ArtEstimate, ArtRevive, ArtTrip } from "../components/landing-art";

/** 半分だけ色が戻った写真。この企画の看板なので、案内ページの一番上に置く。 */
function SignaturePhoto() {
  return (
    <div className="signature">
      <svg viewBox="0 0 440 250" aria-label="左半分が白黒、右半分がカラーになった駅前の写真">
        <defs>
          <linearGradient id="split" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stopColor="#9a938a" />
            <stop offset=".48" stopColor="#9a938a" />
            <stop offset=".52" stopColor="#7fc4bd" />
            <stop offset="1" stopColor="#7fc4bd" />
          </linearGradient>
        </defs>
        <rect width="440" height="250" fill="url(#split)" />
        <circle cx="80" cy="52" r="26" fill="#c9c4bb" />
        <circle cx="360" cy="52" r="26" fill="#f5c542" opacity=".9" />
        <path d="M0 190 L110 90 L200 175 L280 110 L440 200 L440 250 L0 250 Z" fill="#6e675c" />
        <path d="M220 190 L280 110 L440 200 L440 250 L220 250 Z" fill="#4c8a54" />
        <rect x="60" y="150" width="90" height="52" fill="#87817a" />
        <rect x="250" y="150" width="90" height="52" fill="#b9846a" />
        <path d="M52 150 h106 l-12 -22 h-82 z" fill="#6e675c" />
        <path d="M242 150 h106 l-12 -22 h-82 z" fill="#8a5a40" />
        <circle cx="180" cy="196" r="9" fill="#cfc9c0" />
        <rect x="172" y="205" width="16" height="30" rx="7" fill="#a49d93" />
        <circle cx="262" cy="196" r="9" fill="#f0c9a8" />
        <rect x="254" y="205" width="16" height="30" rx="7" fill="#d4694a" />
        <line x1="220" y1="0" x2="220" y2="250" stroke="#fffdf7" strokeWidth="3" strokeDasharray="8 6" />
        <text x="110" y="238" fontSize="13" fill="#efe9df" textAnchor="middle" fontFamily="Kiwi Maru">
          1968年のまま
        </text>
        <text x="330" y="238" fontSize="13" fill="#fffdf7" textAnchor="middle" fontFamily="Kiwi Maru">
          いろどりを再び
        </text>
      </svg>
      <p className="caption">昭和43年　○○駅前にて　—　場所の推定 確度 62%（確定は家族）</p>
    </div>
  );
}

const STORIES = [
  {
    art: <ArtRevive />,
    voice: "「実家に帰るたび、押し入れのアルバムが気になる。でも開くと重たくて、そのまま閉じてしまう」",
    problem:
      "何百枚もの白黒写真。どこから手をつけるか決められないまま、また来年になります。整理しようと思ったときには、写っている場所を知っている人がもういない、ということが起こります。",
    answerTitle: "順番を決める前に、まず色を戻す",
    answer:
      "アルバムのページをスマホで撮って放り込むだけ。ノイズ除去・退色補正・カラー化が自動で通り、待っている間に場所の推定まで進みます。元の写真には触れず、別に保管したまま直します。",
  },
  {
    art: <ArtEstimate />,
    voice: "「これ、どこだっけ」「さあ……昔すぎて忘れちゃった」",
    problem:
      "手がかりは写真の中にあるのに、駅舎や看板を1枚ずつ調べる時間はありません。話が途切れ、写真はまた閉じられます。",
    answerTitle: "決め手を示して、思い出してもらう",
    answer:
      "看板の文字・駅舎の意匠・車両の型式・服装・地形から、撮影地の候補を確度つきで出します。「木造駅舎の妻面が一致」といった根拠まで見せるので、親も記憶をたぐりやすくなります。会話はそのまま録音でき、出てきた人物や出来事が写真に結びついて残ります。",
  },
  {
    art: <ArtTrip />,
    voice: "「たまには親とどこか行きたい。でも行き先はいつも無難な観光地」",
    problem:
      "本当に喜ばれるのは思い出の場所なのに、いまも残っているのか、どう行けばいいのか、歩けるのかが分かりません。",
    answerTitle: "現況を確かめて、無理のない一日にする",
    answer:
      "現存か・建替えか・廃止かを確かめたうえで旅程にします。親の体力に合わせて休憩と昼食が入り、段差やエレベーターの有無も添えます。廃止された場所は、出発前に分かります。",
  },
];

const STEPS: GuideStep[] = [
  {
    phase: "① そろえる",
    title: "はじめる",
    image: "/guide/01-family.png",
    detail: (
      <>
        <kbd>写真をなおす</kbd> を開いて <kbd>写真を入れる</kbd> を押すだけ。
        入れ物（家族とアルバム）はこちらで用意するので、最初に名前を考える必要はありません。
      </>
    ),
  },
  {
    phase: "① そろえる",
    title: "写真を入れる",
    image: "/guide/02-upload.png",
    detail: (
      <>
        開いた画面の点線の枠に写真をドロップするか、タップして選びます。
        何枚でも一度に入れられます。
      </>
    ),
  },
  {
    phase: "① そろえる",
    title: "修復が終わるのを待つ",
    image: "/guide/03-progress.png",
    detail: (
      <>
        入れた直後から、ノイズ除去・退色補正・カラー化と場所の推定が自動で進みます。
        どこまで進んだかはその場に出るので、閉じても構いません。
      </>
    ),
  },
  {
    phase: "② 確かめる",
    title: "仕上がりを見比べて、残す方を選ぶ",
    image: "/guide/04-compare.png",
    detail: (
      <>
        写真を開くと、修復前と後を左右に比べられます。<kbd>カラー化</kbd> と <kbd>復元＋再照明</kbd> を
        切り替えて見て、良い方を <kbd>こちらを採用する</kbd>。
      </>
    ),
  },
  {
    phase: "② 確かめる",
    title: "質問に答えて、場所を確定する",
    image: "/guide/05-confirm.png",
    detail: (
      <>
        右側に AI からの質問と、推定の根拠が並びます。覚えていることを書き、場所を入れて{" "}
        <kbd>家族の記憶として確定する</kbd>。違っていたら訂正欄に書けば、そちらが優先されます。
      </>
    ),
  },
  {
    phase: "② 確かめる",
    title: "語りを残す",
    image: "/guide/06-story.png",
    detail: (
      <>
        写真を見ながら <kbd>● 語りを録音する</kbd> を押して、そのまま話してもらいます。
        書き起こしを貼り付けても構いません。出てきた人物は、
        <kbd>登場人物と出来事を家族として承認する</kbd> を押すまで確定しません。
      </>
    ),
  },
  {
    phase: "② 確かめる",
    title: "写真を少しだけ動かす",
    image: "/guide/07-motion.png",
    detail: (
      <>
        <kbd>ウゴクアルバム</kbd> の欄で、亡くなった家族が写るかを申告して <kbd>ウゴクアルバムを作る</kbd>。
        写る場合は、家族それぞれが <kbd>同意する</kbd> を押し、全員そろって初めて作られます。
      </>
    ),
  },
  {
    phase: "③ 出かける",
    title: "巡礼の旅程を組む",
    image: "/guide/08-trip.png",
    detail: (
      <>
        <kbd>旅をつくる</kbd> を開き、確定した場所の写真を選びます。出発地・日付・
        <kbd>親の体力</kbd> を決めて <kbd>旅程をつくる</kbd>。休憩と昼食が挟まった一日が出ます。
      </>
    ),
  },
  {
    phase: "③ 分かち合う",
    title: "家族に共有する",
    image: "/guide/09-share.png",
    detail: (
      <>
        <kbd>家族に見せる</kbd> でアルバムと期限を選び、<kbd>リンクを作る</kbd>。
        コピーされた URL を、普段の連絡手段で渡すだけです。<kbd>共有を止める</kbd> でいつでも閉じられます。
      </>
    ),
  },
];

export default function LandingPage() {
  return (
    <div className="landing">
      <header className="hero">
        <p className="kicker">思い出カラー化 × 巡礼旅エージェント</p>
        <h1>
          オモイデ<em>工房</em>
        </h1>
        <p className="tagline">
          実家の白黒写真をよみがえらせ、写っている場所を推定し、「もう一度そこへ行く旅」まで組み立てる。
          色を取り戻した思い出を、家族で巡りに行くためのアプリです。
        </p>
        <SignaturePhoto />
      </header>

      <section>
        <h2>こんなこと、ありませんか</h2>
        <div className="story">
          {STORIES.map((s) => (
            <div className="item" key={s.voice}>
              <div className="art">{s.art}</div>
              <div className="body">
                <p className="voice">{s.voice}</p>
                <p>{s.problem}</p>
                <span className="answer">
                  <b>{s.answerTitle}</b>
                  {s.answer}
                </span>
              </div>
            </div>
          ))}
        </div>
        <p className="assurance">
          <b>AI に思い出を作り替えられるのが不安な方へ。</b>
          場所も年代も、AI が出すのは候補です。確定するのは家族で、訂正すればそちらが記録になります。
          写真を動かす機能は、故人が写るなら家族全員の同意が揃うまで動きません。
          預かった写真と語りをモデルの学習に使うこともありません。
        </p>
      </section>

      <section>
        <h2>使い方</h2>
        <p className="lead" style={{ maxWidth: 700, margin: "0 auto 18px" }}>
          画面のボタンをそのまま書いてあります。上から順に進めば、最初の一枚から旅程まで通ります。
        </p>
        <GuideCarousel steps={STEPS} />
      </section>

      <div className="cta">
        <Link className="btn" to="/home">
          写真をなおす
        </Link>
        <p style={{ color: "var(--sub)", fontSize: "0.82rem", marginTop: 10 }}>
          入力は要りません。ボタンひとつで写真を入れる画面まで進み、数分で最初の一枚が色を取り戻します。
        </p>
      </div>
    </div>
  );
}
