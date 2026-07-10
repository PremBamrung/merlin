import { client } from "./client";
import type { components } from "./schema";

// Chat types live with the chat hook (the chat path speaks the Vercel AI SDK
// protocol, not the generated OpenAPI client).
export type { Citation, ChatFilters } from "@/hooks/useAgentChat";

// Domain types — sourced from the generated schema, never hand-written (§2).
export type Item = components["schemas"]["Item"];
export type ListItem = components["schemas"]["ListItem"];
export type ItemList = components["schemas"]["ItemListResponse"];
export type Task = components["schemas"]["Task"];
export type NameCount = components["schemas"]["NameCount"];
export type TimelinePoint = components["schemas"]["TimelinePoint"];
export type Health = components["schemas"]["HealthResponse"];

export type ItemQuery = {
  search?: string;
  source_type?: string;
  status?: string;
  tags?: string[];
  topics?: string[];
  read?: boolean;
  saved?: boolean;
  sort?: string;
  page?: number;
  per_page?: number;
  search_transcripts?: boolean;
};

// Topic taxonomy types (from the generated schema).
export type TopicItem = components["schemas"]["TopicItem"];
export type ItemTopicRef = components["schemas"]["ItemTopicRef"];
export type TopicProposal = components["schemas"]["TopicProposalResponse"];

/** Feed navigation filter — a topic slug (or the "uncategorised" sentinel) plus
 *  optional tag refinement. */
export type FeedFilter = { topics?: string[]; tags?: string[] };

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

// --- Feed: read / saved state ---------------------------------------------
export const markRead = (id: string) => client.post<ListItem>(`/api/items/${id}/read`);
export const markUnread = (id: string) =>
  client.post<ListItem>(`/api/items/${id}/unread`);
export const saveItem = (id: string) => client.post<ListItem>(`/api/items/${id}/save`);
export const unsaveItem = (id: string) =>
  client.post<ListItem>(`/api/items/${id}/unsave`);

export const getUnreadCount = () =>
  client.get<components["schemas"]["CountResponse"]>("/api/items/unread-count");

export const markAllRead = () =>
  client.post<components["schemas"]["CountResponse"]>("/api/items/read-all");

export const getTags = () => client.get<NameCount[]>("/api/tags");
export const getSourceTypes = () => client.get<NameCount[]>("/api/source-types");

// --- Topics (cross-corpus taxonomy) ---------------------------------------
export const getTopics = (status = "active") =>
  client.get<TopicItem[]>("/api/topics", { status });

export const getUncategorisedCount = () =>
  client.get<components["schemas"]["CountResponse"]>(
    "/api/topics/uncategorised-count",
  );

export const createTopic = (body: components["schemas"]["CreateTopicRequest"]) =>
  client.post<TopicItem>("/api/topics", body);

export const patchTopic = (
  id: string,
  body: components["schemas"]["PatchTopicRequest"],
) => client.patch<TopicItem>(`/api/topics/${id}`, body);

export const deleteTopic = (id: string) =>
  client.delete<void>(`/api/topics/${id}`);

export const setItemTopics = (
  id: string,
  body: components["schemas"]["SetItemTopicsRequest"],
) =>
  client.post<components["schemas"]["ItemTopicsResponse"]>(
    `/api/items/${id}/topics`,
    body,
  );

// --- Topic proposals (batch discovery pipeline) ---------------------------
export const getProposals = () =>
  client.get<TopicProposal[]>("/api/topics/proposals");

export const proposeTopics = () =>
  client.post<TaskId>("/api/topics/proposals");

/** Classify the uncategorised backlog against existing topics (background task). */
export const backfillTopics = () =>
  client.post<TaskId>("/api/topics/backfill");

export const acceptProposal = (
  id: string,
  body: components["schemas"]["AcceptProposalRequest"] = {},
) =>
  client.post<components["schemas"]["AcceptProposalResponse"]>(
    `/api/topics/proposals/${id}/accept`,
    body,
  );

export const rejectProposal = (id: string) =>
  client.post<void>(`/api/topics/proposals/${id}/reject`);

// --- Ingest / tasks --------------------------------------------------------
export type TaskId = components["schemas"]["TaskIdResponse"];
export type IngestYouTubeResult = components["schemas"]["IngestYouTubeResponse"];

export const ingestYouTube = (body: components["schemas"]["IngestYouTubeRequest"]) =>
  client.post<IngestYouTubeResult>("/api/ingest/youtube", body);

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

export const cancelTask = (id: string) =>
  client.post<components["schemas"]["CancelTaskResponse"]>(
    `/api/tasks/${id}/cancel`,
  );

// --- Inbox / Digest: failed-ingest management (the Feed replaced review) ----
export type Inbox = components["schemas"]["InboxResponse"];

export const getInbox = (limit = 50) =>
  client.get<Inbox>("/api/digest", { limit });

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
export type Usage = components["schemas"]["UsageResponse"];
export const getUsage = () => client.get<Usage>("/api/insights/usage");

// --- Meta ------------------------------------------------------------------
export const getHealth = () => client.get<Health>("/api/health");
