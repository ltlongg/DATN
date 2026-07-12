import { apiFetch } from "@/api/client";
import type {
  ChunkDetail,
  ChunkListResponse,
  EntityDetail,
  EntityListResponse,
  EventDetail,
  EventListResponse,
} from "@/types/kb";

export interface Page {
  limit?: number;
  offset?: number;
}

export function listChunks(
  params: { q?: string; heading?: string; source_file?: string } & Page,
): Promise<ChunkListResponse> {
  return apiFetch<ChunkListResponse>("/api/admin/kb/chunks", { query: { ...params } });
}

export function getChunk(chunkId: string): Promise<ChunkDetail> {
  return apiFetch<ChunkDetail>(`/api/admin/kb/chunks/${encodeURIComponent(chunkId)}`);
}

export function listEvents(
  params: { q?: string; confidence?: string } & Page,
): Promise<EventListResponse> {
  return apiFetch<EventListResponse>("/api/admin/kb/events", { query: { ...params } });
}

export function getEvent(eventId: string): Promise<EventDetail> {
  return apiFetch<EventDetail>(`/api/admin/kb/events/${encodeURIComponent(eventId)}`);
}

export function listEntities(
  params: { q?: string; type?: string; chunk_id?: string } & Page,
): Promise<EntityListResponse> {
  return apiFetch<EntityListResponse>("/api/admin/kb/entities", { query: { ...params } });
}

export function getEntity(normName: string): Promise<EntityDetail> {
  return apiFetch<EntityDetail>(`/api/admin/kb/entities/${encodeURIComponent(normName)}`);
}
