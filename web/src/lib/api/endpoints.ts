import { client } from "./client";
import type { components } from "./schema";

export type { Citation } from "./client";

// Domain types — sourced from the generated schema, never hand-written (§2).
export type Item = components["schemas"]["Item"];
export type ListItem = components["schemas"]["ListItem"];
export type ItemList = components["schemas"]["ItemListResponse"];
export type Task = components["schemas"]["Task"];
export type NameCount = components["schemas"]["NameCount"];
export type TimelinePoint = components["schemas"]["TimelinePoint"];
export type Health = components["schemas"]["HealthResponse"];
export type ChatMessage = components["schemas"]["ChatMessage"];
export type ChatFilters = components["schemas"]["ChatFilters"];

export type ItemQuery = {
  search?: string;
  source_type?: string;
  status?: string;
  tags?: string[];
  sort?: string;
  page?: number;
  per_page?: number;
};

export type ItemStatus = "queued" | "processing" | "completed" | "failed" | "pending";

// --- Library ---------------------------------------------------------------
export const getItems = (q: ItemQuery = {}) =>
  client.get<ItemList>("/api/items", q);

export const getItem = (id: string) => client.get<Item>(`/api/items/${id}`);

export const updateItem = (
  id: string,
  body: components["schemas"]["UpdateItemRequest"],
) => client.patch<Item>(`/api/items/${id}`, body);

export const deleteItem = (id: string) => client.delete<void>(`/api/items/${id}`);

export const clearSummary = (id: string) =>
  client.post<void>(`/api/items/${id}/clear-summary`);

export const getTags = () => client.get<NameCount[]>("/api/tags");
export const getSourceTypes = () => client.get<NameCount[]>("/api/source-types");

// --- Ingest / tasks --------------------------------------------------------
export type TaskId = components["schemas"]["TaskIdResponse"];

export const ingestYouTube = (body: components["schemas"]["IngestYouTubeRequest"]) =>
  client.post<TaskId>("/api/ingest/youtube", body);

export const resummarize = (
  id: string,
  body: components["schemas"]["ResummarizeRequest"] = {},
) => client.post<TaskId>(`/api/items/${id}/resummarize`, body);

export const retryItem = (
  id: string,
  body: components["schemas"]["RetryRequest"] = {},
) => client.post<TaskId>(`/api/items/${id}/retry`, body);

export const getTasks = (limit = 10) =>
  client.get<Task[]>("/api/tasks", { limit });

export const getTask = (id: string) => client.get<Task>(`/api/tasks/${id}`);

// --- Inbox / Digest --------------------------------------------------------
export type Inbox = components["schemas"]["InboxResponse"];
export type DigestAction = "keep" | "dismiss";

export const getInbox = (limit = 50) =>
  client.get<Inbox>("/api/digest", { limit });

export const digestAction = (id: string, action: DigestAction) =>
  client.post<components["schemas"]["DigestActionResponse"]>(
    `/api/digest/${id}/action`,
    { action },
  );

export const retryFailed = () =>
  client.post<components["schemas"]["RetryFailedResponse"]>("/api/digest/retry-failed");

export const clearFailed = () =>
  client.post<components["schemas"]["ClearFailedResponse"]>("/api/digest/clear-failed");

// --- Insights --------------------------------------------------------------
export const getTimeline = () =>
  client.get<TimelinePoint[]>("/api/insights/timeline");
export const getTopChannels = (limit = 12) =>
  client.get<NameCount[]>("/api/insights/top-channels", { limit });
export const getStatusCounts = () =>
  client.get<NameCount[]>("/api/insights/status-counts");
export const getChannelCount = () =>
  client.get<components["schemas"]["CountResponse"]>("/api/insights/channel-count");

// --- Meta ------------------------------------------------------------------
export const getHealth = () => client.get<Health>("/api/health");
