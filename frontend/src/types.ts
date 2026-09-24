export type InviteStatus = "invited" | "joined" | "revoked";

export interface Member {
  uid: string;
  name: string;
  relation: string;
  invite_status: InviteStatus;
}

export interface Family {
  id: string;
  name: string;
  members: Member[];
  created_at: string;
}

export interface Album {
  id: string;
  family_id: string;
  title: string;
  created_at: string;
}

export interface PlaceCandidate {
  name: string;
  address?: string | null;
  lat?: number | null;
  lng?: number | null;
  confidence: number;
  evidence: string[];
}

export interface EraEstimate {
  label: string;
  year_from?: number | null;
  year_to?: number | null;
  confidence: number;
  evidence: string[];
}

export interface Estimate {
  place_candidates: PlaceCandidate[];
  era?: EraEstimate | null;
  features: string[];
  model: string;
  created_at: string;
}

export interface FamilyQuestion {
  id: string;
  text: string;
  reason: string;
  answered: boolean;
  answer?: string | null;
}

export interface Confirmed {
  place?: string | null;
  era?: string | null;
  confirmed_by?: string | null;
  family_correction?: string | null;
  confirmed_at?: string | null;
}

export type PhotoStatus =
  | "uploaded"
  | "estimating"
  | "awaiting_family"
  | "confirmed"
  | "failed";

export interface Photo {
  id: string;
  album_id: string;
  family_id: string;
  filename: string;
  status: PhotoStatus;
  original_ref?: string | null;
  estimate?: Estimate | null;
  questions: FamilyQuestion[];
  confirmed: Confirmed;
  error?: string | null;
}

export interface Job {
  id: string;
  status: "queued" | "running" | "done" | "failed";
  total: number;
  completed: number;
  steps: string[];
  photo_ids: string[];
  error?: string | null;
}

export type SpotStatus = "existing" | "rebuilt" | "abolished" | "unknown";

export interface Spot {
  photo_id: string;
  place: string;
  current_status: SpotStatus;
  current_note?: string | null;
  stay_minutes: number;
}

export interface Leg {
  kind: "move" | "stay" | "break";
  from?: string | null;
  to?: string | null;
  depart?: string | null;
  arrive?: string | null;
  minutes: number;
  means?: string | null;
  note?: string | null;
}

export interface Itinerary {
  date?: string | null;
  legs: Leg[];
  total_minutes: number;
  walking_minutes: number;
  breaks: number;
  accessibility_notes: string[];
}

export interface Trip {
  id: string;
  family_id: string;
  title: string;
  origin: string;
  date?: string | null;
  stamina: "low" | "normal" | "high";
  spots: Spot[];
  itinerary?: Itinerary | null;
  created_at: string;
}


export interface ShareLink {
  id: string;
  token: string;
  family_id: string;
  target_type: "photo" | "album";
  target_id: string;
  created_by: string;
  expires_at: string;
  revoked: boolean;
  view_count: number;
  created_at: string;
}

export interface SharedView {
  title: string;
  expires_at: string;
  photos: {
    id: string;
    place: string | null;
    era: string | null;
    has_image: boolean;
  }[];
}
