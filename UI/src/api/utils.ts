import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function generateSessionId(length = 40) {
  const bytes = crypto.getRandomValues(new Uint8Array(length));
  const chars = "abcdefghijklmnopqrstuvwxyz";
  let result = "";
  for (let b of bytes) {
    result += chars[b % chars.length];
  }
  return result;
}
