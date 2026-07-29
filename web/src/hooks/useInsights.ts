import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  getTimeline,
  getTopChannels,
  getStatusCounts,
  getChannelCount,
  getUsage,
} from "@/lib/api/endpoints";
import { keys } from "@/lib/queryKeys";

export function useTimeline() {
  return useQuery({
    queryKey: keys.insights("timeline"),
    queryFn: getTimeline,
    placeholderData: keepPreviousData,
    staleTime: 60_000,
  });
}

export function useTopChannels(limit = 12) {
  return useQuery({
    queryKey: keys.insights(`top-channels-${limit}`),
    queryFn: () => getTopChannels(limit),
    placeholderData: keepPreviousData,
    staleTime: 60_000,
  });
}

export function useStatusCounts() {
  return useQuery({
    queryKey: keys.insights("status-counts"),
    queryFn: getStatusCounts,
    placeholderData: keepPreviousData,
    staleTime: 60_000,
  });
}

export function useChannelCount() {
  return useQuery({
    queryKey: keys.insights("channel-count"),
    queryFn: getChannelCount,
    placeholderData: keepPreviousData,
    staleTime: 60_000,
  });
}

export function useUsage() {
  return useQuery({
    queryKey: keys.insights("usage"),
    queryFn: getUsage,
    placeholderData: keepPreviousData,
    staleTime: 60_000,
  });
}
