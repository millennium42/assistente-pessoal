import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BookOpen,
  CalendarDays,
  CloudSun,
  Database,
  FileText,
  LockKeyhole,
  Moon,
  Music2,
  Newspaper,
  RefreshCw,
  Send,
  ShieldCheck,
  Sun,
} from "lucide-react";
import {
  createGoogleCalendarEvent,
  createMemory,
  createStudyNote,
  getGoogleCalendarEvents,
  getGoogleCalendarStatus,
  getDashboard,
  getDataMap,
  getMemories,
  getMusic,
  getNews,
  getWeather,
  saveNewsInterest,
  sendChat,
} from "./api";
import type { NewsItem } from "./api";
import { startSidecarIfDesktop } from "./sidecar";

type PanelState = {
  calendarNotice?: string;
  weather?: string;
  futureWeather?: Array<{
    data: string;
    maxima: string;
    minima: string;
    chance_chuva: string;
  }>;
  news?: string;
  music?: string;
  chat?: string;
  studyNotice?: string;
  newsNotice?: string;
  calendarEventNotice?: string;
};

type ExternalPanelKey = "weather" | "news" | "music";

const NEWS_PAGE_SIZE = 100;

export default function App() {
  const queryClient = useQueryClient();
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [memoryTitle, setMemoryTitle] = useState("");
  const [memoryText, setMemoryText] = useState("");
  const [memoryTags, setMemoryTags] = useState("");
  const [studyTheme, setStudyTheme] = useState("");
  const [studyContent, setStudyContent] = useState("");
  const [chatText, setChatText] = useState("");
  const [eventTitle, setEventTitle] = useState("");
  const [eventStart, setEventStart] = useState("");
  const [eventEnd, setEventEnd] = useState("");
  const [eventDescription, setEventDescription] = useState("");
  const [allowExternalLlm, setAllowExternalLlm] = useState(false);
  const [newsItems, setNewsItems] = useState<NewsItem[]>([]);
  const [newsOffset, setNewsOffset] = useState(0);
  const [panel, setPanel] = useState<PanelState>({});
  const [loadingPanels, setLoadingPanels] = useState<Record<ExternalPanelKey, boolean>>({
    weather: false,
    news: false,
    music: false,
  });
  const [panelErrors, setPanelErrors] = useState<Partial<Record<ExternalPanelKey | "chat", string>>>(
    {},
  );

  const dashboard = useQuery({ queryKey: ["dashboard"], queryFn: getDashboard });
  const memories = useQuery({ queryKey: ["memories"], queryFn: getMemories });
  const dataMap = useQuery({ queryKey: ["data-map"], queryFn: getDataMap });
  const calendarStatus = useQuery({
    queryKey: ["google-calendar-status"],
    queryFn: getGoogleCalendarStatus,
  });
  const calendarEvents = useQuery({
    queryKey: ["google-calendar-events"],
    queryFn: getGoogleCalendarEvents,
    enabled: calendarStatus.data?.connected === true,
  });

  const createMemoryMutation = useMutation({
    mutationFn: () => createMemory(memoryTitle, memoryText, parseTags(memoryTags)),
    onSuccess: async () => {
      setMemoryTitle("");
      setMemoryText("");
      setMemoryTags("");
      await queryClient.invalidateQueries({ queryKey: ["memories"] });
      await queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });

  const createCalendarMutation = useMutation({
    mutationFn: () =>
      createGoogleCalendarEvent({
        titulo: eventTitle,
        inicio: eventStart,
        fim: eventEnd || undefined,
        descricao: eventDescription,
      }),
    onSuccess: async (event) => {
      setEventTitle("");
      setEventStart("");
      setEventEnd("");
      setEventDescription("");
      setPanel((current) => ({
        ...current,
        calendarEventNotice: `Evento criado: ${event.titulo}.`,
      }));
      await queryClient.invalidateQueries({ queryKey: ["google-calendar-events"] });
    },
  });

  const createStudyMutation = useMutation({
    mutationFn: () => createStudyNote(studyTheme, studyContent),
    onSuccess: async (response) => {
      setStudyTheme("");
      setStudyContent("");
      setPanel((current) => ({
        ...current,
        studyNotice: `Nota de estudo criada para ${response.tema}.`,
      }));
      await queryClient.invalidateQueries({ queryKey: ["memories"] });
    },
  });

  const dashboardStatus = dashboard.data?.health.status ?? "carregando";
  const privacyMode = dashboard.data?.privacidade.modo ?? "local-first";
  const memoryCount = memories.data?.length ?? 0;

  const riskLabel = useMemo(() => {
    if (allowExternalLlm) return "envio externo permitido para a proxima conversa";
    return "sem envio externo de contexto";
  }, [allowExternalLlm]);

  useEffect(() => {
    void startSidecarIfDesktop().catch(() => undefined);
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadNews(true);
    }, 700);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("calendar") === "connected") {
      setPanel((current) => ({
        ...current,
        calendarNotice: "Google Agenda conectado com sucesso.",
      }));
      void queryClient.invalidateQueries({ queryKey: ["google-calendar-status"] });
      void queryClient.invalidateQueries({ queryKey: ["google-calendar-events"] });
      window.history.replaceState({}, "", "/");
    }
  }, [queryClient]);

  async function loadExternal(kind: ExternalPanelKey) {
    if (kind === "news") {
      await loadNews(newsItems.length === 0);
      return;
    }
    const loaders = {
      weather: getWeather,
      music: getMusic,
    };
    setLoadingPanels((current) => ({ ...current, [kind]: true }));
    setPanelErrors((current) => ({ ...current, [kind]: undefined }));
    try {
      const response = await loaders[kind]();
      if (kind === "weather") {
        setPanel((current) => ({
          ...current,
          weather: response.texto,
          futureWeather: "futuro" in response ? response.futuro : [],
        }));
        return;
      }
      setPanel((current) => ({ ...current, [kind]: response.texto }));
    } catch (error) {
      const message = error instanceof Error ? error.message : "Falha ao carregar painel.";
      setPanelErrors((current) => ({ ...current, [kind]: message }));
    } finally {
      setLoadingPanels((current) => ({ ...current, [kind]: false }));
    }
  }

  async function loadNews(reset = false) {
    const offset = reset ? 0 : newsOffset;
    setLoadingPanels((current) => ({ ...current, news: true }));
    setPanelErrors((current) => ({ ...current, news: undefined }));
    try {
      const response = await getNews(NEWS_PAGE_SIZE, offset);
      setNewsItems((current) => (reset ? response.itens : [...current, ...response.itens]));
      setNewsOffset(offset + response.itens.length);
      setPanel((current) => ({
        ...current,
        news: response.texto,
        newsNotice: `${offset + response.itens.length} noticias carregadas.`,
      }));
    } catch (error) {
      const message = error instanceof Error ? error.message : "Falha ao carregar painel.";
      setPanelErrors((current) => ({ ...current, news: message }));
    } finally {
      setLoadingPanels((current) => ({ ...current, news: false }));
    }
  }

  async function handleNewsClick(item: NewsItem) {
    const saved = await saveNewsInterest(item);
    setPanel((current) => ({
      ...current,
      newsNotice: `Noticia salva no Obsidian: ${saved.caminho}`,
    }));
    if (item.link) window.open(item.link, "_blank", "noopener,noreferrer");
    await queryClient.invalidateQueries({ queryKey: ["memories"] });
  }

  async function handleChat() {
    if (!chatText.trim()) return;
    setPanelErrors((current) => ({ ...current, chat: undefined }));
    try {
      const response = await sendChat(chatText, allowExternalLlm);
      setPanel((current) => ({ ...current, chat: response.texto }));
      setChatText("");
      setAllowExternalLlm(false);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Falha ao enviar mensagem.";
      setPanelErrors((current) => ({ ...current, chat: message }));
    }
  }

  const dashboardCards = dashboard.data?.cards ?? {};
  const calendarConfigured = calendarStatus.data?.configured ?? false;
  const calendarConnected = calendarStatus.data?.connected ?? false;
  const calendarCredentialLabel = calendarConfigured
    ? `credencial local: ${calendarStatus.data?.credentials_file}`
    : "googleAgenda.json nao encontrado na raiz";
  const calendarStatusText = panel.calendarEventNotice
    ? panel.calendarEventNotice
    : panel.calendarNotice
      ? panel.calendarNotice
      : !calendarConfigured
      ? "Credencial local ausente. O backend continua funcional sem a agenda."
      : calendarConnected
        ? "Agenda conectada no backend local."
        : "Credencial detectada, mas a autenticacao OAuth ainda nao foi concluida.";
  const weatherSummary = panelErrors.weather
    ? panelErrors.weather
    : loadingPanels.weather
      ? "Consultando clima atual e previsao futura..."
      : panel.weather ?? "Aguardando consulta.";
  const newsSummary = panelErrors.news
    ? panelErrors.news
    : loadingPanels.news
      ? "Buscando noticias..."
      : panel.news ?? "Aguardando consulta.";
  const musicSummary = panelErrors.music
    ? panelErrors.music
    : loadingPanels.music
      ? "Buscando lancamentos..."
      : panel.music ?? "Configure artistas para acompanhar lancamentos.";
  const chatSummary = panelErrors.chat ?? panel.chat ?? "Sem conversa iniciada.";

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand-row">
          <div className="brand-mark" aria-label="Logo APPA">
            APPA
          </div>
          <div>
            <p className="eyebrow">Assistente Pessoal V1</p>
            <h1>Dashboard local</h1>
          </div>
        </div>
        <div className="status-strip" aria-label="Estado da aplicacao">
          <span>{dashboardStatus}</span>
          <span>{privacyMode}</span>
          <span>{memoryCount} memorias</span>
          <button
            className="icon-button"
            onClick={() => setTheme((current) => (current === "dark" ? "light" : "dark"))}
            aria-label="Alternar tema"
            title="Alternar tema"
          >
            {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
          </button>
        </div>
      </header>

      <section className="grid">
        <article className="panel span-2">
          <div className="panel-title">
            <ShieldCheck size={18} />
            <h2>Privacidade</h2>
          </div>
          <div className="privacy-row">
            <strong>{riskLabel}</strong>
            <span>
              Chaves, tokens e configuracao bruta ficam no backend local. O dashboard recebe apenas
              dados redigidos.
            </span>
          </div>
          <div className="privacy-row">
            <strong>{Object.keys(dashboardCards).length} cards ativos</strong>
            <span>Clima, noticias, musica, memoria, estudo, chat, agenda e privacidade.</span>
          </div>
          <div className="data-map">
            {(dataMap.data ?? []).slice(0, 4).map((item) => (
              <div key={item.nome}>
                <span>{item.sensibilidade}</span>
                <p>{item.nome}</p>
              </div>
            ))}
          </div>
        </article>

        <article className="panel">
          <div className="panel-title">
            <CalendarDays size={18} />
            <h2>Google Agenda</h2>
            {calendarStatus.data?.configured ? (
              <button
                className="text-button"
                onClick={() => {
                  window.location.assign("http://127.0.0.1:8777/api/google-calendar/auth/start");
                }}
                aria-label="Conectar Google Agenda"
              >
                {calendarStatus.data.connected ? "Reconectar" : "Conectar"}
              </button>
            ) : null}
          </div>
          <p className="mono">{calendarCredentialLabel}</p>
          <p>{calendarStatusText}</p>
          <form
            className="event-form"
            onSubmit={(event) => {
              event.preventDefault();
              if (eventTitle.trim() && eventStart.trim()) createCalendarMutation.mutate();
            }}
          >
            <input
              value={eventTitle}
              onChange={(event) => setEventTitle(event.target.value)}
              placeholder="Titulo do evento"
              aria-label="Titulo do evento"
            />
            <input
              type="datetime-local"
              value={eventStart}
              onChange={(event) => setEventStart(event.target.value)}
              aria-label="Inicio do evento"
            />
            <input
              type="datetime-local"
              value={eventEnd}
              onChange={(event) => setEventEnd(event.target.value)}
              aria-label="Fim do evento"
            />
            <textarea
              value={eventDescription}
              onChange={(event) => setEventDescription(event.target.value)}
              placeholder="Descricao opcional"
              aria-label="Descricao do evento"
            />
            <button type="submit" disabled={!calendarConnected || createCalendarMutation.isPending}>
              <CalendarDays size={16} />
              Criar evento
            </button>
          </form>
          <div className="memory-list">
            {calendarStatus.isLoading ? <span>Verificando integracao...</span> : null}
            {calendarEvents.isLoading ? <span>Carregando proximos eventos...</span> : null}
            {calendarConnected && !calendarEvents.isLoading && (calendarEvents.data?.length ?? 0) === 0 ? (
              <span>Nenhum evento futuro encontrado.</span>
            ) : null}
            {(calendarEvents.data ?? []).slice(0, 4).map((item) => (
              <div key={`${item.titulo}-${item.inicio}`}>
                <strong>{item.titulo}</strong>
                <span>{item.inicio}</span>
              </div>
            ))}
          </div>
        </article>

        <article className="panel">
          <div className="panel-title">
            <CloudSun size={18} />
            <h2>Clima</h2>
            <button
              className="icon-button"
              onClick={() => void loadExternal("weather")}
              aria-label="Atualizar clima"
            >
              <RefreshCw size={16} />
            </button>
          </div>
          <p className="mono">{dashboard.data?.localizacao.cidade ?? "sem localizacao"}</p>
          <p>{weatherSummary}</p>
          <div className="memory-list">
            {!loadingPanels.weather &&
            !panelErrors.weather &&
            (panel.futureWeather?.length ?? 0) === 0 ? (
              <span>Previsao futura aparecera aqui apos a consulta.</span>
            ) : null}
            {(panel.futureWeather ?? []).map((item) => (
              <div key={item.data}>
                <strong>{item.data}</strong>
                <span>
                  max {item.maxima} C, min {item.minima} C, chuva {item.chance_chuva}%
                </span>
              </div>
            ))}
          </div>
        </article>

        <article className="panel">
          <div className="panel-title">
            <Newspaper size={18} />
            <h2>Noticias</h2>
            <button
              className="icon-button"
              onClick={() => void loadExternal("news")}
              aria-label="Atualizar noticias"
            >
              <RefreshCw size={16} />
            </button>
          </div>
          <p className="mono">{panel.newsNotice ?? newsSummary}</p>
          <div className="news-list">
            {newsItems.length === 0 && !loadingPanels.news ? (
              <span>Nenhuma noticia carregada ainda.</span>
            ) : null}
            {newsItems.map((item) => (
              <div className="news-item" key={`${item.fonte}-${item.link}-${item.titulo}`}>
                <strong>{item.titulo}</strong>
                <span>{item.fonte}</span>
                {item.resumo ? <p>{item.resumo}</p> : null}
                <div className="row-actions">
                  <button onClick={() => void handleNewsClick(item)}>Abrir e salvar</button>
                  <button
                    onClick={() =>
                      void saveNewsInterest(item).then(async (saved) => {
                        setPanel((current) => ({
                          ...current,
                          newsNotice: `Noticia salva no Obsidian: ${saved.caminho}`,
                        }));
                        await queryClient.invalidateQueries({ queryKey: ["memories"] });
                      })
                    }
                  >
                    Salvar
                  </button>
                </div>
              </div>
            ))}
          </div>
          <button onClick={() => void loadNews(false)} disabled={loadingPanels.news}>
            {loadingPanels.news ? "Carregando..." : "Carregar mais"}
          </button>
        </article>

        <article className="panel">
          <div className="panel-title">
            <Music2 size={18} />
            <h2>Musica</h2>
            <button
              className="icon-button"
              onClick={() => void loadExternal("music")}
              aria-label="Atualizar musica"
            >
              <RefreshCw size={16} />
            </button>
          </div>
          <pre>{musicSummary}</pre>
        </article>

        <article className="panel span-2">
          <div className="panel-title">
            <BookOpen size={18} />
            <h2>Estudo</h2>
          </div>
          <form
            className="memory-form"
            onSubmit={(event) => {
              event.preventDefault();
              if (studyTheme.trim() && studyContent.trim()) createStudyMutation.mutate();
            }}
          >
            <input
              value={studyTheme}
              onChange={(event) => setStudyTheme(event.target.value)}
              placeholder="Tema"
              aria-label="Tema de estudo"
            />
            <textarea
              value={studyContent}
              onChange={(event) => setStudyContent(event.target.value)}
              placeholder="Material para resumir e gerar perguntas"
              aria-label="Conteudo de estudo"
            />
            <button type="submit">
              <BookOpen size={16} />
              Criar nota
            </button>
          </form>
          <div className="chat-output">
            {createStudyMutation.isPending
              ? "Gerando nota de estudo..."
              : panel.studyNotice ??
                "Gera resumo local ou com LLM configurado, conforme permissao."}
          </div>
        </article>

        <article className="panel span-2">
          <div className="panel-title">
            <Database size={18} />
            <h2>Memoria</h2>
          </div>
          <form
            className="memory-form"
            onSubmit={(event) => {
              event.preventDefault();
              if (memoryTitle.trim() && memoryText.trim()) createMemoryMutation.mutate();
            }}
          >
            <input
              value={memoryTitle}
              onChange={(event) => setMemoryTitle(event.target.value)}
              placeholder="Titulo"
              aria-label="Titulo da memoria"
            />
            <textarea
              value={memoryText}
              onChange={(event) => setMemoryText(event.target.value)}
              placeholder="Conteudo local"
              aria-label="Conteudo da memoria"
            />
            <input
              value={memoryTags}
              onChange={(event) => setMemoryTags(event.target.value)}
              placeholder="Tags separadas por virgula"
              aria-label="Tags da memoria"
            />
            <button type="submit">
              <FileText size={16} />
              Salvar
            </button>
          </form>
          <div className="memory-list">
            {memories.isLoading ? <span>Carregando memorias...</span> : null}
            {!memories.isLoading && (memories.data?.length ?? 0) === 0 ? (
              <span>Nenhuma memoria local salva ainda.</span>
            ) : null}
            {(memories.data ?? []).slice(0, 6).map((item) => (
              <div key={item.caminho}>
                <strong>{item.titulo}</strong>
                <span>{item.trecho}</span>
              </div>
            ))}
          </div>
        </article>

        <article className="panel span-2">
          <div className="panel-title">
            <LockKeyhole size={18} />
            <h2>Chat</h2>
          </div>
          <div className="chat-output">{chatSummary}</div>
          <label className="toggle">
            <input
              type="checkbox"
              checked={allowExternalLlm}
              onChange={(event) => setAllowExternalLlm(event.target.checked)}
            />
            Permitir envio externo nesta mensagem
          </label>
          <div className="chat-input">
            <input
              value={chatText}
              onChange={(event) => setChatText(event.target.value)}
              placeholder="Mensagem"
              aria-label="Mensagem para o assistente"
              onKeyDown={(event) => {
                if (event.key === "Enter") void handleChat();
              }}
            />
            <button onClick={() => void handleChat()} aria-label="Enviar mensagem">
              <Send size={16} />
            </button>
          </div>
        </article>
      </section>

      <footer>
        Desenvolvimento assistido por IA documentado. Revisao humana, testes e controles locais
        continuam obrigatorios.
      </footer>
    </main>
  );
}

function parseTags(value: string): string[] {
  return value
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean);
}
