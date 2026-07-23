export type ThemeName = "light" | "dark" | "pink" | "blue";

export type User = {
  id: number;
  username: string;
};

export type AuthResponse = {
  access_token: string;
  token_type: string;
  user: User;
};

export type StorySummary = {
  id: number;
  title: string;
  language: string;
  topic: string;
  is_read: boolean;
  created_at: string;
};

export type Story = StorySummary & {
  content: string;
  illustrations: StoryIllustration[];
};

export type StoryIllustration = {
  id: number;
  chapter_index: number;
  chapter_text: string;
  image_url: string | null;
  status: "pending" | "generating" | "ready" | "failed" | "unavailable";
  error: string | null;
};

export type StoryCreate = {
  language: string;
  topic: string;
  extra_prompt: string;
};

export type StoryTopic = {
  topic: string;
  source: string;
};

export type StoryTopics = {
  topics: string[];
  source: string;
};

export type AIConfig = {
  base_url: string;
  model: string;
  image_base_url: string;
  image_model: string;
  image_headers: string;
  headers: string;
  extra_prompt: string;
  has_api_key: boolean;
  has_image_api_key: boolean;
};

export type AIConfigUpdate = {
  base_url: string;
  model: string;
  image_base_url: string;
  image_model: string;
  image_headers: string;
  headers: string;
  extra_prompt: string;
  api_key?: string | null;
  image_api_key?: string | null;
  clear_api_key?: boolean;
  clear_image_api_key?: boolean;
};

const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api";

async function request<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(normalizeError(body.detail));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

function normalizeError(detail: unknown): string {
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    return "请求参数不正确，请检查输入内容";
  }
  return "请求失败，请稍后再试";
}

export const api = {
  register(username: string, password: string) {
    return request<AuthResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ username, password })
    });
  },
  login(username: string, password: string) {
    return request<AuthResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password })
    });
  },
  getAIConfig(token: string) {
    return request<AIConfig>("/ai-config", {}, token);
  },
  saveAIConfig(token: string, payload: AIConfigUpdate) {
    return request<AIConfig>("/ai-config", {
      method: "PUT",
      body: JSON.stringify(payload)
    }, token);
  },
  listStories(token: string, query: string) {
    const params = query.trim() ? `?query=${encodeURIComponent(query.trim())}` : "";
    return request<StorySummary[]>(`/stories${params}`, {}, token);
  },
  getStory(token: string, id: number) {
    return request<Story>(`/stories/${id}`, {}, token);
  },
  generateStoryIllustrations(token: string, id: number) {
    return request<Story>(`/stories/${id}/illustrations`, { method: "POST" }, token);
  },
  createStory(token: string, payload: StoryCreate) {
    return request<Story>("/stories", {
      method: "POST",
      body: JSON.stringify(payload)
    }, token);
  },
  markRead(token: string, id: number) {
    return request<Story>(`/stories/${id}/read`, { method: "PATCH" }, token);
  },
  deleteStory(token: string, id: number) {
    return request<void>(`/stories/${id}`, { method: "DELETE" }, token);
  },
  randomStoryTopics(token: string, count = 4) {
    return request<StoryTopics>(`/story-topics/random?count=${count}`, {}, token);
  },
  mediaUrl(path: string) {
    return API_BASE.startsWith("http") ? new URL(path, API_BASE).toString() : path;
  }
};
