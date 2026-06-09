function apiBaseUrl(): string {
  if ("__TAURI_INTERNALS__" in window) return "http://127.0.0.1:8777/api";
  return "/api";
}

const API_BASE = apiBaseUrl();

export type Dashboard = {
  health: {
    status: string;
    version: string;
    vault_configurado: boolean;
    llm_configurado: boolean;
  };
  localizacao: {
    cidade: string;
    timezone: string;
  };
  memorias_recentes: MemorySummary[];
  google_calendar: GoogleCalendarStatus;
  cards: Record<string, Record<string, boolean | number | string>>;
  privacidade: {
    modo: string;
    envio_llm_exige_opt_in: boolean;
  };
};

export type GoogleCalendarStatus = {
  configured: boolean;
  connected: boolean;
  credentials_file: string;
  token_present: boolean;
};

export type MemorySummary = {
  titulo: string;
  caminho: string;
  criado_em: string;
  trecho: string;
};

export type TextResponse = {
  texto: string;
  quantidade?: string;
};

export type NewsItem = {
  titulo: string;
  link: string;
  fonte: string;
  publicado: string;
  resumo: string;
};

export type NewsResponse = TextResponse & {
  itens: NewsItem[];
  offset: number;
  assuntos_interesse: string[];
};

export type WeatherFutureItem = {
  data: string;
  maxima: string;
  minima: string;
  chance_chuva: string;
};

export type WeatherResponse = {
  texto: string;
  cidade: string;
  futuro: WeatherFutureItem[];
};

export type ChatResponse = {
  texto: string;
  llm_usado: boolean;
  opt_in_necessario?: boolean;
  modelo?: string;
};

export type DataMapItem = {
  nome: string;
  categoria: string;
  sensibilidade: string;
  finalidade: string;
  armazenamento: string;
  retencao: string;
  compartilhamento_externo: string;
  base_legal_sugerida: string;
};

export type CalendarEvent = {
  titulo: string;
  inicio: string;
  link: string;
};

export async function getDashboard(): Promise<Dashboard> {
  return request("/dashboard");
}

export async function getMemories(): Promise<MemorySummary[]> {
  return request("/memories");
}

export async function createMemory(
  titulo: string,
  conteudo: string,
  tags: string[] = [],
): Promise<{ caminho: string }> {
  return request("/memories", {
    method: "POST",
    body: JSON.stringify({ titulo, conteudo, tags }),
  });
}

export async function createStudyNote(
  tema: string,
  conteudo: string,
): Promise<{ caminho: string; tema: string }> {
  return request("/study-notes", {
    method: "POST",
    body: JSON.stringify({ tema, conteudo, perguntas: 5 }),
  });
}

export async function getWeather(): Promise<WeatherResponse> {
  return request("/weather");
}

export async function getNews(limite = 100, offset = 0): Promise<NewsResponse> {
  return request(`/news?limite=${limite}&offset=${offset}`);
}

export async function saveNewsInterest(item: NewsItem): Promise<{ caminho: string }> {
  return request("/news/interest", {
    method: "POST",
    body: JSON.stringify({ ...item, tags: ["dashboard"] }),
  });
}

export async function getMusic(): Promise<TextResponse> {
  return request("/music");
}

export async function sendChat(
  mensagem: string,
  permitirLlmExterno: boolean,
): Promise<ChatResponse> {
  return request("/chat", {
    method: "POST",
    body: JSON.stringify({ mensagem, permitir_llm_externo: permitirLlmExterno }),
  });
}

export async function getDataMap(): Promise<DataMapItem[]> {
  return request("/privacy/data-map");
}

export async function getGoogleCalendarStatus(): Promise<GoogleCalendarStatus> {
  return request("/google-calendar/status");
}

export async function getGoogleCalendarEvents(): Promise<CalendarEvent[]> {
  return request("/google-calendar/events");
}

export async function createGoogleCalendarEvent(payload: {
  titulo: string;
  inicio: string;
  fim?: string;
  descricao?: string;
}): Promise<CalendarEvent> {
  return request("/google-calendar/events", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Falha HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}
