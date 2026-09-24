import type { DehydratedState } from "@tanstack/react-query";

const CACHE_KEY = `v2:${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}`;

export interface SavedJobs { savedAt: number; state: DehydratedState }

function openCache(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open("jobslave-cache", 1);
    request.onupgradeneeded = () => request.result.createObjectStore("queries");
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export async function readJobCache(): Promise<SavedJobs | undefined> {
  const db = await openCache();
  try {
    return await new Promise((resolve, reject) => {
      const request = db.transaction("queries").objectStore("queries").get(CACHE_KEY);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  } finally { db.close(); }
}

export async function writeJobCache(saved: SavedJobs): Promise<void> {
  const db = await openCache();
  try {
    await new Promise<void>((resolve, reject) => {
      const transaction = db.transaction("queries", "readwrite");
      transaction.objectStore("queries").put(saved, CACHE_KEY);
      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(transaction.error);
      transaction.onabort = () => reject(transaction.error);
    });
  } finally { db.close(); }
}
