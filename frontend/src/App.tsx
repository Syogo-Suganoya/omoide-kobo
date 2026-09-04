import { NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";

import { MainNav } from "./components/nav";
import { FamilyProvider, useFamily } from "./family";
import AlbumPage from "./pages/AlbumPage";
import DashboardPage from "./pages/DashboardPage";
import LandingPage from "./pages/LandingPage";
import PhotoPage from "./pages/PhotoPage";
import SharePage from "./pages/SharePage";
import SharedPage from "./pages/SharedPage";
import TripPage from "./pages/TripPage";

function FamilySwitcher() {
  const { families, family, select } = useFamily();
  if (families.length < 2) return null;
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
        <div className="bar">
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
              <span className="spacer" />
              <FamilySwitcher />
              <NavLink to="/" end className="guide-link">
                使い方
              </NavLink>
            </>
          )}
        </div>
        {!shared && <MainNav />}
      </header>

      <main className="wrap">
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/home" element={<DashboardPage />} />
          <Route path="/albums/:albumId" element={<AlbumPage />} />
          <Route path="/photos/:photoId" element={<PhotoPage />} />
          <Route path="/trip" element={<TripPage />} />
          <Route path="/share" element={<SharePage />} />
          <Route path="/s/:token" element={<SharedPage />} />
          {/* 旧パスからの取りこぼしを拾う */}
          <Route path="/albums" element={<Navigate to="/home" replace />} />
          <Route path="/governance" element={<Navigate to="/share" replace />} />
          <Route path="*" element={<Navigate to="/home" replace />} />
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
