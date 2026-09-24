"use client";

import { useEffect, useState } from "react";

import { api } from "../lib/api";

export function useResource<T>(path: string | null) {
  const [result, setResult] = useState<{
    path: string;
    attempt: number;
    data: T;
  }>();
  const [failedRequest, setFailedRequest] = useState<string>();
  const [attempt, setAttempt] = useState(0);

  const requestKey = path === null ? null : `${path}:${attempt}`;

  useEffect(() => {
    if (path === null) return;

    let active = true;
    const currentAttempt = attempt;

    api<T>(path)
      .then(data => {
        if (!active) return;
        setResult({
          path,
          attempt: currentAttempt,
          data,
        });
        setFailedRequest(undefined);
      })
      .catch(() => {
        if (active) {
          setFailedRequest(`${path}:${currentAttempt}`);
        }
      });

    return () => {
      active = false;
    };
  }, [path, attempt]);

  const succeeded =
    path !== null &&
    result?.path === path &&
    result.attempt === attempt;

  const failed =
    requestKey !== null &&
    failedRequest === requestKey;

  return {
    data: result?.path === path ? result.data : undefined,
    failed,
    loading: path !== null && !succeeded && !failed,
    retry: () => setAttempt(value => value + 1),
  };
}