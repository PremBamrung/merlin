import { useQuery } from "@tanstack/react-query";
import {
  getTimeline,
  getTopChannels,
  getStatusCounts,
  getChannelCount,
} from "@/lib/api/endpoints";
import { keys } from "@/lib/queryKeys";

export function useTimeline() {
  return useQuery({
    queryKey: keys.insights("timeline"),
    queryFn: getTimeline,
    staleTime: 60_000,
  });
}

export function useTopChannels(limit = 12) {
  return useQuery({
    queryKey: keys.insights(`top-channels-${limit}`),
    queryFn: () => getTopChannels(limit),
    staleTime: 60_000,
  });
}

export function useStatusCounts() {
  return useQuery({
    queryKey: keys.insights("status-counts"),
    queryFn: getStatusCounts,
    staleTime: 60_000,
  });
}

export function useChannelCount() {
  return useQuery({
    queryKey: keys.insights("channel-count"),
    queryFn: getChannelCount,
    staleTime: 60_000,
  });
}
