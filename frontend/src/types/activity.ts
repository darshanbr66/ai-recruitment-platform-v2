/** Mirrors backend/app/schemas/activity.py. */

export interface ActivityResponse {
  id: string;
  actor_name: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  entity_label: string | null;
  description: string | null;
  reason: string | null;
  created_at: string;
}

export interface ActivityDeleteResult {
  deleted: number;
}

export interface ActivityCount {
  total: number;
}
