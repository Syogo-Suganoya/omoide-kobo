/** 案内ページの挿絵。写真と同じ紙もの・フラットな配色で、文章より先に中身が伝わるように描く。 */

const PAPER = "#fffdf7";
const KRAFT = "#e7d9bd";
const LINE = "#dccdaa";
const BROWN = "#5c4a35";
const SUB = "#8a7a63";
const IRO = "#2e968c";
const AKA = "#d4694a";
const GRAY = "#9a938a";

/** 積まれたままのアルバムから、色が戻った1枚が抜き出される。 */
export function ArtRevive() {
  return (
    <svg viewBox="0 0 260 170" role="img" aria-label="閉じたアルバムの山から、色が戻った写真が1枚取り出される">
      <rect x="14" y="104" width="104" height="16" rx="2" fill={BROWN} opacity=".55" />
      <rect x="18" y="88" width="96" height="16" rx="2" fill={BROWN} opacity=".75" />
      <rect x="12" y="72" width="106" height="18" rx="2" fill={BROWN} />
      <rect x="26" y="76" width="78" height="3" rx="1.5" fill={KRAFT} opacity=".8" />
      <text x="66" y="140" fontSize="11" fill={SUB} textAnchor="middle" fontFamily="Kiwi Maru">
        開かれないまま
      </text>

      <path d="M126 92 h30" stroke={LINE} strokeWidth="2" strokeDasharray="5 4" />
      <path d="M150 87 l8 5 -8 5 z" fill={AKA} />

      <g transform="rotate(-4 220 78)">
        <rect x="166" y="34" width="88" height="86" fill={PAPER} stroke={LINE} />
        <rect x="173" y="41" width="74" height="52" fill="#7fc4bd" />
        <circle cx="232" cy="54" r="7" fill="#f5c542" />
        <path d="M173 93 L196 62 L214 82 L228 68 L247 93 Z" fill="#4c8a54" />
        <rect x="186" y="76" width="20" height="17" fill="#b9846a" />
        <path d="M183 76 h26 l-4 -7 h-18 z" fill="#8a5a40" />
        <text x="210" y="110" fontSize="9" fill={SUB} textAnchor="middle" fontFamily="Kiwi Maru">
          いろどりが戻る
        </text>
      </g>
      <rect x="196" y="26" width="46" height="12" rx="1" fill={AKA} opacity=".32" transform="rotate(-8 219 32)" />
    </svg>
  );
}

/** 写真の中の手がかりを拾い、候補を確度つきで並べる。 */
export function ArtEstimate() {
  return (
    <svg viewBox="0 0 260 170" role="img" aria-label="写真の看板や駅舎から手がかりを拾い、候補が確度つきで並ぶ">
      <rect x="10" y="24" width="104" height="94" fill={PAPER} stroke={LINE} />
      <rect x="17" y="31" width="90" height="66" fill={GRAY} />
      <rect x="34" y="62" width="42" height="28" fill="#7d766e" />
      <path d="M30 62 h50 l-7 -11 h-36 z" fill="#645d55" />
      <rect x="46" y="49" width="26" height="8" rx="1" fill={PAPER} opacity=".9" />
      <circle cx="59" cy="53" r="9" fill="none" stroke={AKA} strokeWidth="2" />
      <path d="M65 59 l7 7" stroke={AKA} strokeWidth="2" strokeLinecap="round" />
      <text x="62" y="110" fontSize="9" fill={SUB} textAnchor="middle" fontFamily="Kiwi Maru">
        看板・駅舎・車両
      </text>

      <path d="M120 66 h16" stroke={LINE} strokeWidth="2" strokeDasharray="5 4" />
      <path d="M132 61 l8 5 -8 5 z" fill={AKA} />

      <g fontFamily="Kiwi Maru" fontSize="9">
        <rect x="146" y="30" width="106" height="30" fill={PAPER} stroke={LINE} />
        <rect x="146" y="30" width="3" height="30" fill={IRO} />
        <text x="155" y="44" fill={BROWN}>
          会津柳津駅
        </text>
        <rect x="155" y="49" width="62" height="5" rx="2.5" fill={KRAFT} />
        <rect x="155" y="49" width="38" height="5" rx="2.5" fill={IRO} />
        <text x="223" y="54" fill={SUB}>
          62%
        </text>

        <rect x="146" y="66" width="106" height="26" fill={PAPER} stroke={LINE} />
        <rect x="146" y="66" width="3" height="26" fill={LINE} />
        <text x="155" y="79" fill={SUB}>
          山都駅
        </text>
        <rect x="155" y="83" width="62" height="4" rx="2" fill={KRAFT} />
        <rect x="155" y="83" width="15" height="4" rx="2" fill={LINE} />
        <text x="223" y="88" fill={SUB}>
          24%
        </text>
      </g>
      <text x="199" y="110" fontSize="9" fill={AKA} textAnchor="middle" fontFamily="Kiwi Maru">
        確定するのは家族
      </text>
    </svg>
  );
}

/** 思い出の場所を、休憩を挟んでつなぐ一日。 */
export function ArtTrip() {
  return (
    <svg viewBox="0 0 260 170" role="img" aria-label="出発地から思い出の場所へ、休憩を挟んでつながる旅程">
      <path
        d="M26 104 C 70 104, 66 48, 108 48 S 168 108, 208 60"
        fill="none"
        stroke={LINE}
        strokeWidth="3"
        strokeDasharray="7 6"
      />
      <g fontFamily="Kiwi Maru" fontSize="9" fill={SUB} textAnchor="middle">
        <circle cx="26" cy="104" r="8" fill={BROWN} />
        <text x="26" y="126">自宅</text>

        <circle cx="108" cy="48" r="10" fill={IRO} />
        <path d="M103 48 h10 M108 43 v10" stroke={PAPER} strokeWidth="2" />
        <text x="108" y="30">思い出の駅</text>
        <text x="108" y="70" fill={IRO}>
          現存
        </text>

        <rect x="146" y="88" width="26" height="16" rx="3" fill={AKA} opacity=".85" />
        <text x="159" y="100" fill={PAPER} fontSize="8">
          休憩
        </text>

        <circle cx="208" cy="60" r="10" fill={IRO} />
        <path d="M203 60 h10 M208 55 v10" stroke={PAPER} strokeWidth="2" />
        <text x="208" y="42">商店街</text>
        <text x="208" y="82" fill={SUB}>
          建替え済み
        </text>
      </g>
      <text x="130" y="150" fontSize="10" fill={BROWN} textAnchor="middle" fontFamily="Kiwi Maru">
        乗換すくなめ・休憩ありの一日
      </text>
    </svg>
  );
}
