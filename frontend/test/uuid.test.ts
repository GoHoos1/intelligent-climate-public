import { describe, expect, it, vi } from "vitest";

import { createUuid } from "../src/util/uuid";

describe("schedule UUID compatibility", () => {
  it("prefers the native randomUUID implementation when available", () => {
    const randomUUID = vi.fn(
      (): `${string}-${string}-${string}-${string}-${string}` =>
        "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    );
    const getRandomValues = vi.fn();

    expect(createUuid({ randomUUID, getRandomValues })).toBe(
      "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    );
    expect(randomUUID).toHaveBeenCalledOnce();
    expect(getRandomValues).not.toHaveBeenCalled();
  });

  it("creates a valid version 4 UUID with getRandomValues on plain HTTP", () => {
    const getRandomValues = vi.fn((bytes: Uint8Array) => {
      bytes.set(Array.from({ length: 16 }, (_, index) => index));
      return bytes;
    });

    expect(
      createUuid({ getRandomValues } as Pick<Crypto, "getRandomValues">),
    ).toBe("00010203-0405-4607-8809-0a0b0c0d0e0f");
    expect(getRandomValues).toHaveBeenCalledOnce();
  });
});
