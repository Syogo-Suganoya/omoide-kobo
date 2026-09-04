import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api";
import { ErrorBar } from "../components/bits";
import { useFamily } from "../family";
import type { Album, Photo, Trip } from "../types";

const STAMINA = [
  { value: "low", label: "ゆっくり（休憩多め）" },
  { value: "normal", label: "ふつう" },
  { value: "high", label: "しっかり歩ける" },
];

const SPOT_LABEL: Record<string, string> = {
  existing: "現存",
  rebuilt: "建替え・改称",
  abolished: "廃止・消失",
  unknown: "現況不明",
};

export default function TripPage() {
  const { family } = useFamily();
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [trips, setTrips] = useState<Trip[]>([]);
  const [trip, setTrip] = useState<Trip | null>(null);
  const [origin, setOrigin] = useState("東京");
  const [date, setDate] = useState("");
  const [startTime, setStartTime] = useState("09:00");
  const [stamina, setStamina] = useState("low");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(async () => {
    if (!family) return;
    const albums: Album[] = await api.listAlbums(family.id);
    const lists = await Promise.all(albums.map((a) => api.listPhotos(a.id)));
    setPhotos(lists.flat().filter((p) => p.confirmed.place));
    setTrips(await api.listTrips(family.id));
  }, [family]);

  useEffect(() => {
    load().catch(setError);
  }, [load]);

  const toggle = (id: string) =>
    setSelected((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]));

  const plan = async () => {
    if (!family) return;
    setBusy(true);
    setError(null);
    try {
      const created = await api.createTrip({
        family_id: family.id,
        photo_ids: selected,
        origin,
        date: date || undefined,
        stamina,
        start_time: startTime,
      });
      setTrip(created);
      await load();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  if (!family) return <div className="empty">先に家族をつくってください。</div>;

  return (
    <>
      <ErrorBar error={error} />

      <section className="block">
        <h2>思い出の場所を選ぶ</h2>
        <p className="lead">
          <b>写真をタップすると選べます（何枚でも）。</b>
          家族が確定した場所だけが旅程に組めます。現況（現存・建替え・廃止）を確かめてから、
          休憩を織り込んだ経路にします。
        </p>
        {photos.length === 0 ? (
          <div className="empty">
            場所が確定した写真がまだありません。
            <div className="row" style={{ justifyContent: "center", marginTop: 12 }}>
              <Link className="btn small" to="/home">
                写真の場所を確かめに行く
              </Link>
            </div>
          </div>
        ) : (
          <div className="grid">
            {photos.map((photo, i) => {
              const on = selected.includes(photo.id);
              return (
                <button
                  key={photo.id}
                  type="button"
                  aria-pressed={on}
                  className={`polaroid pick ${on ? "on" : ""} ${i % 2 ? "tilt-b" : "tilt-a"}`}
                  onClick={() => toggle(photo.id)}
                >
                  <img src={api.imageUrl(photo.id, "restored")} alt={photo.filename} />
                  <span className="mark">{on ? `✓ ${selected.indexOf(photo.id) + 1}番目` : "選ぶ"}</span>
                  <span className="cap">{photo.confirmed.place}</span>
                </button>
              );
            })}
          </div>
        )}
        {photos.length > 0 && (
          <p style={{ color: "var(--sub)", fontSize: "0.82rem", marginTop: 12 }}>
            {selected.length === 0
              ? "まだ1か所も選ばれていません。"
              : `${selected.length}か所を選びました。タップした順に訪ねます。`}
          </p>
        )}
      </section>

      <section className="block">
        <h2>旅の条件</h2>
        <div className="card">
          <div className="row">
            <div style={{ flex: 1, minWidth: 160 }}>
              <span className="label">出発地</span>
              <input value={origin} onChange={(e) => setOrigin(e.target.value)} />
            </div>
            <div style={{ flex: 1, minWidth: 140 }}>
              <span className="label">日付</span>
              <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </div>
            <div style={{ flex: 1, minWidth: 120 }}>
              <span className="label">出発時刻</span>
              <input type="time" value={startTime} onChange={(e) => setStartTime(e.target.value)} />
            </div>
            <div style={{ flex: 1, minWidth: 180 }}>
              <span className="label">親の体力</span>
              <select value={stamina} onChange={(e) => setStamina(e.target.value)}>
                {STAMINA.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="row" style={{ marginTop: 14, alignItems: "center" }}>
            <button className="btn" disabled={busy || selected.length === 0} onClick={plan}>
              {busy
                ? "組み立てています…"
                : selected.length === 0
                  ? "旅程をつくる"
                  : `${selected.length}か所の旅程をつくる`}
            </button>
            {/* 押せない理由を、押す前に言う */}
            {selected.length === 0 && !busy && (
              <span style={{ color: "var(--aka)", fontSize: "0.82rem" }}>
                ↑ 上の写真を1枚以上選ぶと押せます
              </span>
            )}
          </div>
        </div>
      </section>

      {trip?.itinerary && (
        <section className="block">
          <h2>{trip.title}</h2>
          <div className="row" style={{ marginBottom: 12 }}>
            <span className="chip iro">所要 {Math.floor(trip.itinerary.total_minutes / 60)}時間
              {trip.itinerary.total_minutes % 60}分</span>
            <span className="chip">徒歩 {trip.itinerary.walking_minutes}分</span>
            <span className="chip aka">休憩 {trip.itinerary.breaks}回</span>
          </div>

          <div className="card" style={{ marginBottom: 16 }}>
            <h3>訪ねる場所の現況</h3>
            <table>
              <thead>
                <tr>
                  <th>場所</th>
                  <th>現況</th>
                  <th>メモ</th>
                  <th>滞在</th>
                </tr>
              </thead>
              <tbody>
                {trip.spots.map((spot) => (
                  <tr key={spot.photo_id}>
                    <td style={{ color: "var(--ink)" }}>{spot.place}</td>
                    <td>{SPOT_LABEL[spot.current_status]}</td>
                    <td>{spot.current_note}</td>
                    <td>{spot.stay_minutes}分</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <ul className="timeline">
            {trip.itinerary.legs.map((leg, i) => (
              <li key={i} className={leg.kind}>
                <span className="time">{leg.depart}</span>
                <span className="what">
                  {leg.kind === "stay"
                    ? `${leg.to} に滞在（${leg.minutes}分）`
                    : leg.kind === "break"
                      ? `${leg.means}（${leg.minutes}分）`
                      : `${leg.means}で ${leg.from} → ${leg.to}（${leg.minutes}分）`}
                </span>
                {leg.note && <div className="note">{leg.note}</div>}
              </li>
            ))}
          </ul>

          {trip.itinerary.accessibility_notes.length > 0 && (
            <div className="card" style={{ marginTop: 16 }}>
              <h3>体力・バリアフリーの配慮</h3>
              <ul className="evidence">
                {trip.itinerary.accessibility_notes.map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}

      {trips.length > 0 && (
        <section className="block">
          <h2>これまでの旅程</h2>
          <div className="grid">
            {trips.map((t) => (
              <button key={t.id} className="card tight" onClick={() => setTrip(t)} type="button">
                <h3 style={{ marginBottom: 4 }}>{t.title}</h3>
                <p style={{ color: "var(--sub)", fontSize: "0.8rem" }}>
                  {t.origin} 発 ／ {t.spots.length}か所 ／ 休憩 {t.itinerary?.breaks ?? 0}回
                </p>
              </button>
            ))}
          </div>
        </section>
      )}
    </>
  );
}
