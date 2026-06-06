const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function postAlign({ sessionId, featureText, signal }) {
  const response = await fetch(`${API_BASE_URL}/align`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      feature_text: featureText,
    }),
    signal,
  });
  return response;
}
