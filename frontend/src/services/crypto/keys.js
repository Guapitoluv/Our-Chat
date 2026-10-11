const ECDH = {
  name: "ECDH",
  namedCurve: "P-256"
};

export async function generateKeyPair() {
  const pair = await crypto.subtle.generateKey(
    ECDH,
    true,
    ["deriveKey"]
  );

  const publicKey = await crypto.subtle.exportKey(
    "jwk",
    pair.publicKey
  );

  const privateKey = await crypto.subtle.exportKey(
    "jwk",
    pair.privateKey
  );

  return { publicKey, privateKey };
}

export async function importPublicKey(jwk) {
  return crypto.subtle.importKey(
    "jwk",
    jwk,
    ECDH,
    true,
    []
  );
}

export async function importPrivateKey(jwk) {
  return crypto.subtle.importKey(
    "jwk",
    jwk,
    ECDH,
    false,
    ["deriveKey"]
  );
}