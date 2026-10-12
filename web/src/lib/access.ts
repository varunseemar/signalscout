"use client";

import useSWR from "swr";
import { fetcher } from "./api";

type Access = { read_only: boolean; is_admin: boolean };

/** Public demo is read-only; editing needs the admin key (stored after visiting /?admin=KEY). */
export function useAccess() {
  const { data, mutate } = useSWR<Access>("/api/config", fetcher, { revalidateOnFocus: false });
  return {
    canEdit: data ? !data.read_only || data.is_admin : false,
    readOnly: data?.read_only ?? false,
    isAdmin: data?.is_admin ?? false,
    refresh: mutate,
  };
}
