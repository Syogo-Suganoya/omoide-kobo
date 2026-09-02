import type {
  AgentsResponse,
  Album,
  AuditLog,
  Family,
  Job,
  MotionClip,
  Photo,
  SharedView,
  ShareLink,
  Trip,
} from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: init?.body instanceof FormData ? undefined : { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`${res.status} ${detail}`);
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

const json = (body: unknown) => JSON.stringify(body);

export const api = {
  agents: () => request<AgentsResponse>("/agents"),

  listFamilies: () => request<Family[]>("/families"),
  createFamily: (name: string) => request<Family>("/families", { method: "POST", body: json({ name }) }),
  getFamily: (id: string) => request<Family>(`/families/${id}`),
  inviteMember: (id: string, name: string, relation: string) =>
    request<Family>(`/families/${id}/members`, { method: "POST", body: json({ name, relation }) }),
  updateInvite: (id: string, uid: string, status: string) =>
    request<Family>(`/families/${id}/members/${uid}`, { method: "POST", body: json({ status }) }),
  deleteFamily: (id: string) => request<{ deleted: boolean }>(`/families/${id}`, { method: "DELETE" }),

  listAlbums: (familyId: string) => request<Album[]>(`/families/${familyId}/albums`),
  createAlbum: (familyId: string, title: string) =>
    request<Album>("/albums", { method: "POST", body: json({ family_id: familyId, title }) }),
  getAlbum: (id: string) => request<Album>(`/albums/${id}`),
  listPhotos: (albumId: string) => request<Photo[]>(`/albums/${albumId}/photos`),

  upload: (albumId: string, files: File[]) => {
    const form = new FormData();
    files.forEach((file) => form.append("files", file));
    return request<{ job: Job; photos: Photo[] }>(`/albums/${albumId}/photos`, {
      method: "POST",
      body: form,
    });
  },
  getJob: (id: string) => request<Job>(`/jobs/${id}`),

  getPhoto: (id: string) => request<Photo>(`/photos/${id}`),
  imageUrl: (id: string, kind: "original" | "restored" | "alt") =>
    `${BASE}/photos/${id}/image/${kind}`,
  chooseVariant: (id: string, variant: "restored" | "alt", chosen_by: string) =>
    request<Photo>(`/photos/${id}/variant`, { method: "POST", body: json({ variant, chosen_by }) }),
  confirmPhoto: (
    id: string,
    payload: {
      place?: string;
      era?: string;
      family_correction?: string;
      confirmed_by: string;
      answers?: { question_id: string; answer: string }[];
    }
  ) => request<Photo>(`/photos/${id}/confirm`, { method: "POST", body: json(payload) }),
  reestimate: (id: string) => request<Photo>(`/photos/${id}/reestimate`, { method: "POST" }),
  addStoryText: (id: string, transcript: string, narrator?: string) =>
    request<Photo>(`/photos/${id}/story/text`, { method: "POST", body: json({ transcript, narrator }) }),
  addStoryAudio: (id: string, blob: Blob, narrator?: string) => {
    const form = new FormData();
    form.append("audio", blob, "talk.webm");
    if (narrator) form.append("narrator", narrator);
    return request<Photo>(`/photos/${id}/story`, { method: "POST", body: form });
  },
  confirmStory: (id: string, payload: { confirmed_by: string; people: string[]; events: string[] }) =>
    request<Photo>(`/photos/${id}/story/confirm`, { method: "POST", body: json(payload) }),

  listTrips: (familyId: string) => request<Trip[]>(`/families/${familyId}/trips`),
  getTrip: (id: string) => request<Trip>(`/trips/${id}`),
  createTrip: (payload: {
    family_id: string;
    photo_ids: string[];
    origin: string;
    date?: string;
    stamina: string;
    start_time?: string;
  }) => request<Trip>("/trips", { method: "POST", body: json(payload) }),

  requestMotion: (photoId: string, requested_by: string, includes_deceased: boolean) =>
    request<MotionClip>(`/photos/${photoId}/motion`, {
      method: "POST",
      body: json({ requested_by, includes_deceased }),
    }),
  listMotions: (photoId: string) => request<MotionClip[]>(`/photos/${photoId}/motions`),
  decideConsent: (motionId: string, uid: string, status: "granted" | "denied") =>
    request<MotionClip>(`/motions/${motionId}/consent`, { method: "POST", body: json({ uid, status }) }),
  motionVideoUrl: (motionId: string) => `${BASE}/motions/${motionId}/video`,

  audit: (familyId: string) => request<AuditLog[]>(`/families/${familyId}/audit`),

  createShare: (payload: {
    family_id: string;
    target_type: "photo" | "album";
    target_id: string;
    created_by: string;
    days: number;
  }) => request<{ link: ShareLink; path: string }>("/share", { method: "POST", body: json(payload) }),
  listShares: (familyId: string) => request<ShareLink[]>(`/families/${familyId}/shares`),
  revokeShare: (token: string) => request<ShareLink>(`/shares/${token}/revoke`, { method: "POST" }),
  viewShared: (token: string) => request<SharedView>(`/shared/${token}`),
  sharedImageUrl: (token: string, photoId: string) => `${BASE}/shared/${token}/photos/${photoId}/image`,
};
