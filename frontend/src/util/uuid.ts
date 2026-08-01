type UuidCrypto = Pick<Crypto, "getRandomValues"> &
  Partial<Pick<Crypto, "randomUUID">>;

/** Create an RFC 4122 version 4 UUID, including on non-secure HTTP origins. */
export function createUuid(cryptoApi: UuidCrypto = globalThis.crypto): string {
  if (typeof cryptoApi.randomUUID === "function") {
    return cryptoApi.randomUUID();
  }

  const bytes = cryptoApi.getRandomValues(new Uint8Array(16));
  bytes[6] = ((bytes[6] ?? 0) & 0x0f) | 0x40;
  bytes[8] = ((bytes[8] ?? 0) & 0x3f) | 0x80;
  const hexadecimal = Array.from(bytes, (value) =>
    value.toString(16).padStart(2, "0"),
  );
  return `${hexadecimal.slice(0, 4).join("")}-${hexadecimal.slice(4, 6).join("")}-${hexadecimal.slice(6, 8).join("")}-${hexadecimal.slice(8, 10).join("")}-${hexadecimal.slice(10).join("")}`;
}
