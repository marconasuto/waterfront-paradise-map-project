/**
 * Runtime-validated env. Vite exposes only `VITE_*` vars to the client.
 * Throwing here is the right move: a missing public token means an empty
 * map, which is worse than a clear "set VITE_MAPBOX_PUBLIC_TOKEN" error.
 */

export interface AppEnv {
  mapboxPublicToken: string;
}

export function loadEnv(): AppEnv {
  const token = import.meta.env.VITE_MAPBOX_PUBLIC_TOKEN ?? "";
  if (!token) {
    throw new Error(
      "VITE_MAPBOX_PUBLIC_TOKEN is not set. Copy webapp/.env.example to webapp/.env and add your `pk.*` token.",
    );
  }
  return { mapboxPublicToken: token };
}
