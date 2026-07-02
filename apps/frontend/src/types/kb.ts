/** Types KB Inspector (Module 5). Mirror apps/backend/app/schemas/inspect.py +
 *  apps/agent-service/app/schemas/kb.py. */

export interface EventRef {
  event_id: string;
  label: string;
  time_start?: string | null;
  time_end?: string | null;
  confidence: string;
}

export interface ChunkListItem {
  chunk_id: string;
  heading_path: string[];
  source_file?: string | null;
  start_line?: number | null;
  end_line?: number | null;
  preview: string;
}

export interface ChunkListResponse {
  items: ChunkListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface ChunkDetail {
  chunk_id: string;
  text: string;
  metadata: Record<string, unknown>;
  heading_path: string[];
  referencing_events: EventRef[];
}

export interface EventListItem {
  event_id: string;
  label: string;
  time_start?: string | null;
  time_end?: string | null;
  locations: string[];
  confidence: string;
}

export interface EventListResponse {
  items: EventListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface EventDetail {
  event_id: string;
  label: string;
  summary: string;
  time_start?: string | null;
  time_end?: string | null;
  locations: string[];
  confidence: string;
  parent_event_norm?: string | null;
  source_chunk_ids: string[];
}

export interface EntityListItem {
  name: string;
  norm_name: string;
  type?: string | null;
  description_count: number;
  source_chunk_count: number;
}

export interface EntityListResponse {
  items: EntityListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface EntityNeighbor {
  name?: string | null;
  norm_name?: string | null;
  type?: string | null;
}

export interface EntityEdge {
  source_name?: string | null;
  source_norm?: string | null;
  target_name?: string | null;
  target_norm?: string | null;
  keyword?: string | null;
  description: string;
  source_chunk_ids: string[];
}

export interface EntityDetail {
  name: string;
  norm_name: string;
  type?: string | null;
  descriptions: string[];
  source_chunk_ids: string[];
  neighbors: EntityNeighbor[];
  edges: EntityEdge[];
}
