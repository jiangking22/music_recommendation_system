export const dynamic = "force-dynamic";

type Item = { id: string; title: string; artist: string; explanation: string };

async function loadRecommendations(seed: string): Promise<Item[]> {
  const api = process.env.API_INTERNAL_URL ?? "http://localhost:8000";
  const response = await fetch(`${api}/v1/recommendations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ seed, limit: 3 }),
    cache: "no-store",
    signal: AbortSignal.timeout(3000),
  });
  if (!response.ok) throw new Error("Recommendation API unavailable");
  const payload: unknown = await response.json();
  if (!isRecommendationResponse(payload)) throw new Error("Invalid API response");
  return payload.items;
}

function isRecommendationResponse(value: unknown): value is { items: Item[] } {
  if (typeof value !== "object" || value === null || !("items" in value)) return false;
  const items = value.items;
  return Array.isArray(items) && items.every((item) =>
    item !== null && typeof item === "object" &&
    typeof item.id === "string" && typeof item.title === "string" &&
    typeof item.artist === "string" && typeof item.explanation === "string");
}

export default async function Home({ searchParams }: { searchParams: Promise<{ seed?: string | string[] }> }) {
  const requestedSeed = (await searchParams).seed;
  const seed = (typeof requestedSeed === "string" ? requestedSeed.trim().slice(0, 120) : "") || "jazz";
  let items: Item[] = [];
  let unavailable = false;
  try {
    items = await loadRecommendations(seed);
  } catch {
    unavailable = true;
  }

  return (
    <main>
      <h1>Music recommendation</h1>
      <p>Phase 1 fixture examples</p>
      <form method="get">
        <label htmlFor="seed">Seed</label>{" "}
        <input id="seed" name="seed" defaultValue={seed} maxLength={120} />
        <button type="submit">Show examples</button>
      </form>
      {unavailable ? <p role="alert">Recommendation API is unavailable.</p> : (
        <ul>{items.map((item) => <li key={item.id}><strong>{item.title}</strong> — {item.artist}. {item.explanation}</li>)}</ul>
      )}
    </main>
  );
}
