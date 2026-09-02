import { NavLink, Route, Routes, useLocation } from "react-router-dom";

import { FamilyProvider, useFamily } from "./family";
import AlbumPage from "./pages/AlbumPage";
import GovernancePage from "./pages/GovernancePage";
import HomePage from "./pages/HomePage";
import PhotoPage from "./pages/PhotoPage";
import SharedPage from "./pages/SharedPage";
import TripPage from "./pages/TripPage";

function FamilySwitcher() {
  const { families, family, select } = useFamily();
  if (families.length === 0) return null;
  return (
    <select
      style={{ width: "auto", padding: "5px 10px", fontSize: "0.8rem" }}
      value={family?.id ?? ""}
      onChange={(e) => select(e.target.value)}
      aria-label="家族を切り替え"
    >
      {families.map((f) => (
        <option key={f.id} value={f.id}>
          {f.name}
        </option>
      ))}
    </select>
  );
}

function Shell() {
  // 共有リンクの閲覧者に家族の操作メニューは見せない
  const shared = useLocation().pathname.startsWith("/s/");

  return (
    <div className="app">
      <header className="topbar">
        {shared ? (
          <span className="brand">
            オモイデ<em>工房</em>
          </span>
        ) : (
          <NavLink to="/" className="brand">
            オモイデ<em>工房</em>
          </NavLink>
        )}
        {!shared && (
          <>
            <nav>
              <NavLink to="/" end>
                アルバム
              </NavLink>
              <NavLink to="/trip">巡礼旅</NavLink>
              <NavLink to="/governance">共有と記録</NavLink>
            </nav>
            <span className="spacer" />
            <FamilySwitcher />
          </>
        )}
      </header>

      <main className="wrap">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/albums/:albumId" element={<AlbumPage />} />
          <Route path="/photos/:photoId" element={<PhotoPage />} />
          <Route path="/trip" element={<TripPage />} />
          <Route path="/governance" element={<GovernancePage />} />
          <Route path="/s/:token" element={<SharedPage />} />
        </Routes>
      </main>

      <footer className="foot">
        {shared
          ? "家族が期限つきで共有した思い出です。期限が過ぎるか、家族が共有を止めると見られなくなります。"
          : "写真と語りは家族限定の領域に保存され、モデルの学習には使いません。推定は候補であり、確定はいつでも家族の記憶が優先されます。"}
      </footer>
    </div>
  );
}

export default function App() {
  return (
    <FamilyProvider>
      <Shell />
    </FamilyProvider>
  );
}
