export const MAX_QUESTION_LENGTH = 500;

const API_URL = import.meta.env.VITE_API_URL ?? "";

export interface Source {
  citation: string;
  url: string;
}

export interface AskResponse {
  answer: string;
  answerable: boolean;
  unanswered_parts: string;
  sources: Source[];
}

/** Carries a message that is safe to show to the visitor. */
export class AskError extends Error {}

export async function askQuestion(question: string): Promise<AskResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/api/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
  } catch {
    throw new AskError("Sunucuya ulaşılamadı. Bağlantınızı kontrol edip tekrar deneyin.");
  }

  if (response.ok) {
    return (await response.json()) as AskResponse;
  }
  throw new AskError(await readErrorMessage(response));
}

async function readErrorMessage(response: Response): Promise<string> {
  try {
    const body: { detail?: unknown } = await response.json();
    // Validation errors arrive as a list, and only plain strings are written for visitors.
    return typeof body.detail === "string"
      ? body.detail
      : "Cevap üretilemedi. Lütfen tekrar deneyin.";
  } catch {
    // Our API always answers with JSON, so anything else came from a proxy in front of it.
    return "Sunucuya ulaşılamadı. Lütfen biraz sonra tekrar deneyin.";
  }
}
