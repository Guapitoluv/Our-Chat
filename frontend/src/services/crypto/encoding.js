/*
 * Este codigo é responsavel por converter bytes e json
 * Isso porque criptografia trabalha com bytes, nao texto
 */

export function toBase64(bytes) {
  let binary = "";

  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }

  return btoa(binary);
}

export function fromBase64(value) {
  const binary = atob(value);

  return Uint8Array.from(
    binary,
    character => character.charCodeAt(0)
  );
}