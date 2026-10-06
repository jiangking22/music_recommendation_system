import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

vi.mock("next/navigation", () => {
  const router = { replace: vi.fn(), refresh: vi.fn() };
  return { useRouter: () => router, usePathname: () => "/" };
});

afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.unstubAllGlobals();
});
