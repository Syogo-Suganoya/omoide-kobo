import { NavLink } from "react-router-dom";

/**
 * 上部のメニュー。
 * 「押すと何ができるか」が分かるように、名詞ではなく動詞を出し、
 * 一行の説明を添える。狭い画面では下端に回して親指で押せる位置に置く。
 */

function IconPhoto() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="M3 16l5-5 4 4 3-3 6 6" />
      <circle cx="8.5" cy="9.5" r="1.4" />
    </svg>
  );
}

function IconTrip() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 21s7-6.3 7-11a7 7 0 1 0-14 0c0 4.7 7 11 7 11z" />
      <circle cx="12" cy="10" r="2.6" />
    </svg>
  );
}

function IconShare() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M3 6h18v12H3z" />
      <path d="M3 7l9 6 9-6" />
    </svg>
  );
}

const ITEMS = [
  {
    to: "/home",
    icon: <IconPhoto />,
    label: "写真を調べる",
    hint: "アルバムと、次にやること",
  },
  {
    to: "/trip",
    icon: <IconTrip />,
    label: "旅をつくる",
    hint: "思い出の場所をめぐる",
  },
  {
    to: "/share",
    icon: <IconShare />,
    label: "家族に見せる",
    hint: "招待と共有リンク",
  },
];

export function MainNav() {
  return (
    <nav className="mainnav" aria-label="やることメニュー">
      {ITEMS.map((item) => (
        <NavLink key={item.to} to={item.to} className="tab">
          <span className="ico">{item.icon}</span>
          <span className="txt">
            <b>{item.label}</b>
            <small>{item.hint}</small>
          </span>
        </NavLink>
      ))}
    </nav>
  );
}
