import React, { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowUp,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  Eye,
  EyeOff,
  ChevronsDown,
  ChevronsUp,
  KeyRound,
  LoaderCircle,
  LogOut,
  Moon,
  Palette,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Shuffle,
  Save,
  Search,
  Settings2,
  Sparkles,
  Sun,
  Trash2,
  UserPlus,
  X
} from "lucide-react";
import { api, AIConfig, AuthResponse, Story, StorySummary, ThemeName, User } from "./api";
import "./styles.css";

const themes: { name: ThemeName; label: string }[] = [
  { name: "light", label: "明亮" },
  { name: "dark", label: "黑暗" },
  { name: "pink", label: "粉色" },
  { name: "blue", label: "蓝色" }
];

const languages = [
  { value: "zh", label: "中文" },
  { value: "en", label: "English" },
  { value: "bilingual", label: "中英双语" }
];

const prenatalStoryTopics = [
  "懂礼貌的小兔子",
  "爱洗手的小花猫",
  "愿意分享玩具的小熊",
  "诚实去上学的小白熊",
  "帮妈妈整理房间的小猴",
  "认真洗水果的小猪",
  "知错就改的小象",
  "会说谢谢的小松鼠",
  "不乱跑的小鸭子",
  "勤劳种花的小兔",
  "排队喝水的小鹿",
  "轻轻说话的小刺猬",
  "爱护图书的小熊猫",
  "把椅子放好的小老虎",
  "睡前收玩具的小狐狸",
  "慢慢吃饭的小海豚"
];

const emptyAIConfig: AIConfig = {
  base_url: "https://api.openai.com/v1",
  model: "gpt-4o-mini",
  headers: "{}",
  extra_prompt: "",
  has_api_key: false
};

function withTimeout<T>(promise: Promise<T>, milliseconds: number): Promise<T> {
  return Promise.race([
    promise,
    new Promise<T>((_, reject) => {
      window.setTimeout(() => reject(new Error("请求超时，请稍后再试")), milliseconds);
    })
  ]);
}

function pickLocalTopic(currentTopic: string) {
  const nextTopics = prenatalStoryTopics.filter((item) => item !== currentTopic);
  const pool = nextTopics.length ? nextTopics : prenatalStoryTopics;
  return pool[Math.floor(Math.random() * pool.length)];
}

function getErrorMessage(err: unknown, fallback: string) {
  return err instanceof Error ? err.message : fallback;
}

function useMediaQuery(query: string) {
  const [matches, setMatches] = useState(() => (
    typeof window === "undefined" ? false : window.matchMedia(query).matches
  ));

  useEffect(() => {
    const media = window.matchMedia(query);
    const update = () => setMatches(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, [query]);

  return matches;
}

function App() {
  const [theme, setTheme] = useState<ThemeName>(() => (localStorage.getItem("theme") as ThemeName) || "pink");
  const [token, setToken] = useState(() => localStorage.getItem("token") || "");
  const [user, setUser] = useState<User | null>(() => {
    const saved = localStorage.getItem("user");
    return saved ? JSON.parse(saved) : null;
  });
  const [stories, setStories] = useState<StorySummary[]>([]);
  const [selected, setSelected] = useState<Story | null>(null);
  const [aiConfig, setAIConfig] = useState<AIConfig>(emptyAIConfig);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [storyPanelCollapsed, setStoryPanelCollapsed] = useState(false);
  const [query, setQuery] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [storiesLoading, setStoriesLoading] = useState(false);
  const [configLoading, setConfigLoading] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [readingId, setReadingId] = useState<number | null>(null);
  const isMobileLayout = useMediaQuery("(max-width: 880px)");
  const panelToggleTitle = storyPanelCollapsed
    ? isMobileLayout ? "向下展开故事工作台" : "向右展开故事工作台"
    : isMobileLayout ? "向上收起故事工作台" : "向左收起故事工作台";

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("theme", theme);
  }, [theme]);

  useEffect(() => {
    if (token) {
      loadStories();
      loadAIConfig();
    }
  }, [token]);

  async function loadStories(search = query) {
    if (!token) return;
    setStoriesLoading(true);
    try {
      const data = await api.listStories(token, search);
      setStories(data);
      if (selected && !data.some((item) => item.id === selected.id)) {
        setSelected(null);
      }
    } catch (err) {
      setMessage(getErrorMessage(err, "故事列表加载失败"));
    } finally {
      setStoriesLoading(false);
    }
  }

  async function loadAIConfig() {
    if (!token) return;
    setConfigLoading(true);
    try {
      setAIConfig(await api.getAIConfig(token));
    } catch (err) {
      setMessage(getErrorMessage(err, "AI 配置加载失败"));
    } finally {
      setConfigLoading(false);
    }
  }

  function handleAuth(auth: AuthResponse) {
    setToken(auth.access_token);
    setUser(auth.user);
    localStorage.setItem("token", auth.access_token);
    localStorage.setItem("user", JSON.stringify(auth.user));
    setMessage(`欢迎，${auth.user.username}`);
  }

  function logout() {
    setToken("");
    setUser(null);
    setStories([]);
    setSelected(null);
    setSettingsOpen(false);
    localStorage.removeItem("token");
    localStorage.removeItem("user");
  }

  async function selectStory(id: number) {
    if (!token) return;
    setLoading(true);
    try {
      setSelected(await api.getStory(token, id));
      setSettingsOpen(false);
    } catch (err) {
      setMessage(getErrorMessage(err, "故事加载失败"));
    } finally {
      setLoading(false);
    }
  }

  async function deleteStory(id: number) {
    if (!token) return;
    setDeletingId(id);
    try {
      await api.deleteStory(token, id);
      setStories((items) => items.filter((story) => story.id !== id));
      if (selected?.id === id) setSelected(null);
      setMessage("故事已删除");
    } catch (err) {
      setMessage(getErrorMessage(err, "故事删除失败"));
    } finally {
      setDeletingId(null);
    }
  }

  async function onRead(id: number) {
    if (!token) return;
    setReadingId(id);
    try {
      const updated = await api.markRead(token, id);
      setSelected(updated);
      setStories((items) => items.map((story) => story.id === id ? { ...story, is_read: true } : story));
    } catch (err) {
      setMessage(getErrorMessage(err, "已读状态更新失败"));
    } finally {
      setReadingId(null);
    }
  }

  if (!token || !user) {
    return (
      <AuthScreen
        onAuth={handleAuth}
        theme={theme}
        setTheme={setTheme}
        message={message}
        clearMessage={() => setMessage("")}
      />
    );
  }

  return (
    <main className="app-shell">
      <Toast message={message} onClose={() => setMessage("")} />
      <header className="topbar">
        <div className="brand-lockup" aria-label="Moon Sprout Stories">
          <span className="brand-mark"><Sparkles size={22} /></span>
          <div>
            <p className="eyebrow">Moon Sprout Stories</p>
            <h1>胎教故事生成器</h1>
          </div>
        </div>
        <div className="top-actions">
          <button
            className={settingsOpen ? "icon-text ghost active" : "icon-text ghost"}
            onClick={() => {
              setStoryPanelCollapsed(false);
              setSettingsOpen((value) => !value);
            }}
            aria-label={settingsOpen ? "关闭 AI 配置" : "打开 AI 配置"}
            title={settingsOpen ? "关闭 AI 配置" : "打开 AI 配置"}
          >
            {settingsOpen ? <X size={18} /> : <Settings2 size={18} />}
          </button>
          <ThemePicker theme={theme} setTheme={setTheme} />
          <button className="icon-text ghost" onClick={logout}>
            <LogOut size={18} />
            <span>{user.username}</span>
          </button>
        </div>
      </header>

      <section className={storyPanelCollapsed ? "workspace panel-collapsed" : "workspace"}>
        <aside className={storyPanelCollapsed ? "story-panel collapsed" : "story-panel"}>
          <div className="panel-control-row">
            {!storyPanelCollapsed && <span>故事工作台</span>}
            <button
              className="panel-collapse-button"
              type="button"
              onClick={() => setStoryPanelCollapsed((value) => !value)}
              aria-label={panelToggleTitle}
              title={panelToggleTitle}
            >
              {storyPanelCollapsed
                ? isMobileLayout ? <ChevronsDown size={18} /> : <PanelLeftOpen size={18} />
                : isMobileLayout ? <ChevronsUp size={18} /> : <PanelLeftClose size={18} />}
            </button>
          </div>

          {!storyPanelCollapsed && (
            <>
              {settingsOpen && (
                <AIConfigPanel
                  token={token}
                  config={aiConfig}
                  loading={configLoading}
                  onSaved={(config) => {
                    setAIConfig(config);
                    setMessage("AI 配置已保存");
                  }}
                />
              )}

              <StoryCreator
                token={token}
                onCreated={(story) => {
                  setSelected(story);
                  setStories((items) => [story, ...items]);
                  setSettingsOpen(false);
                  setMessage("新的睡前小故事已经准备好了");
                }}
                onError={(text) => setMessage(text)}
                setLoading={setLoading}
              />

              <form
                className="search-row"
                onSubmit={(event) => {
                  event.preventDefault();
                  loadStories(query);
                }}
              >
                <Search size={18} />
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="搜索主题或标题"
                />
                <button className="small-button" type="submit" disabled={storiesLoading}>
                  {storiesLoading ? <LoaderCircle className="spin" size={16} /> : "查找"}
                </button>
              </form>

              <StoryList
                stories={stories}
                selectedId={selected?.id}
                loading={storiesLoading}
                deletingId={deletingId}
                onSelect={selectStory}
                onDelete={deleteStory}
              />
            </>
          )}
        </aside>

        <StoryReader
          story={selected}
          loading={loading}
          markingRead={selected ? readingId === selected.id : false}
          onRead={onRead}
        />
      </section>
    </main>
  );
}

function AuthScreen({
  onAuth,
  theme,
  setTheme,
  message,
  clearMessage
}: {
  onAuth: (auth: AuthResponse) => void;
  theme: ThemeName;
  setTheme: (theme: ThemeName) => void;
  message: string;
  clearMessage: () => void;
}) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const auth = mode === "login"
        ? await api.login(username, password)
        : await api.register(username, password);
      onAuth(auth);
    } catch (err) {
      setError(err instanceof Error ? err.message : "操作失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-stage">
      <Toast
        message={error || message}
        type={error ? "error" : "info"}
        onClose={() => {
          setError("");
          clearMessage();
        }}
      />
      <div className="auth-visual">
        <div className="paper-moon" />
        <h1>Moon Sprout Stories</h1>
        <p>为宝宝胎教生成简单、温柔、可反复阅读的中英文小故事。</p>
      </div>
      <section className="auth-card">
        <div className="auth-card-head">
          <div>
            <p className="eyebrow">开始使用</p>
            <h2>{mode === "login" ? "登录" : "注册"}</h2>
          </div>
          <ThemePicker theme={theme} setTheme={setTheme} compact />
        </div>

        <div className="segmented">
          <button className={mode === "login" ? "active" : ""} onClick={() => setMode("login")} type="button">
            <Moon size={16} /> 登录
          </button>
          <button className={mode === "register" ? "active" : ""} onClick={() => setMode("register")} type="button">
            <UserPlus size={16} /> 注册
          </button>
        </div>

        <form className="auth-form" onSubmit={submit}>
          <label>
            用户名
            <input value={username} onChange={(event) => setUsername(event.target.value)} minLength={3} required />
          </label>
          <label>
            密码
            <div className="password-row">
              <input
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                minLength={5}
                type={showPassword ? "text" : "password"}
                required
              />
              <button
                className="icon-only soft-action"
                type="button"
                onClick={() => setShowPassword((value) => !value)}
                aria-label={showPassword ? "隐藏密码" : "显示密码"}
                title={showPassword ? "隐藏密码" : "显示密码"}
              >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </label>
          <button className="primary-button" disabled={loading}>
            {loading ? <LoaderCircle className="spin" size={18} /> : <Sparkles size={18} />}
            {loading ? "处理中..." : mode === "login" ? "进入故事屋" : "创建账号"}
          </button>
        </form>
      </section>
    </main>
  );
}

function ThemePicker({
  theme,
  setTheme,
  compact = false
}: {
  theme: ThemeName;
  setTheme: (theme: ThemeName) => void;
  compact?: boolean;
}) {
  return (
    <div className={compact ? "theme-picker compact" : "theme-picker"} aria-label="主题切换">
      <Palette size={18} />
      {themes.map((item) => (
        <button
          key={item.name}
          className={theme === item.name ? "selected" : ""}
          onClick={() => setTheme(item.name)}
          title={item.label}
          type="button"
        >
          <span className={`swatch ${item.name}`} />
        </button>
      ))}
    </div>
  );
}

function AIConfigPanel({
  token,
  config,
  loading,
  onSaved
}: {
  token: string;
  config: AIConfig;
  loading: boolean;
  onSaved: (config: AIConfig) => void;
}) {
  const [baseUrl, setBaseUrl] = useState(config.base_url);
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState(config.model);
  const [headers, setHeaders] = useState(config.headers);
  const [extraPrompt, setExtraPrompt] = useState(config.extra_prompt);
  const [clearKey, setClearKey] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setBaseUrl(config.base_url);
    setModel(config.model);
    setHeaders(config.headers);
    setExtraPrompt(config.extra_prompt);
    setApiKey("");
    setClearKey(false);
  }, [config]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setSaving(true);
    try {
      const parsedHeaders = JSON.parse(headers || "{}");
      if (!parsedHeaders || Array.isArray(parsedHeaders) || typeof parsedHeaders !== "object") {
        setError("Headers 必须是合法的 JSON 对象");
        return;
      }
      const saved = await api.saveAIConfig(token, {
        base_url: baseUrl,
        api_key: apiKey || null,
        model,
        headers: headers || "{}",
        extra_prompt: extraPrompt,
        clear_api_key: clearKey
      });
      onSaved(saved);
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存失败，请稍后再试");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="ai-config-panel" onSubmit={submit}>
      <Toast message={error} type="error" onClose={() => setError("")} />
      <div className="creator-title">
        <span><KeyRound size={18} /></span>
        <div>
          <p className="eyebrow">Model Settings</p>
          <h2>AI 配置</h2>
        </div>
      </div>

      {loading && (
        <p className="inline-loading"><LoaderCircle className="spin" size={16} /> AI 配置加载中...</p>
      )}

      <label>
        Base URL
        <input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} disabled={loading || saving} required />
      </label>

      <label>
        API Key
        <input
          value={apiKey}
          onChange={(event) => setApiKey(event.target.value)}
          placeholder={config.has_api_key ? "已保存，留空则保持不变" : "请输入 API Key"}
          type="password"
          disabled={loading || saving}
        />
      </label>

      {config.has_api_key && (
        <label className="check-row">
          <input type="checkbox" checked={clearKey} onChange={(event) => setClearKey(event.target.checked)} disabled={loading || saving} />
          清空已保存的 API Key
        </label>
      )}

      <label>
        模型名称
        <input value={model} onChange={(event) => setModel(event.target.value)} disabled={loading || saving} required />
      </label>

      <label>
        Headers JSON
        <textarea value={headers} onChange={(event) => setHeaders(event.target.value)} disabled={loading || saving} rows={4} />
      </label>

      <label>
        全局补充提示词
        <textarea
          value={extraPrompt}
          onChange={(event) => setExtraPrompt(event.target.value)}
          disabled={loading || saving}
          rows={4}
          placeholder="例如：更有音乐感，不出现惊吓情节；也可以写“控制在 800 字左右”。"
        />
      </label>

      <button className="primary-button" disabled={loading || saving}>
        {saving ? <LoaderCircle className="spin" size={18} /> : <Save size={18} />}
        {saving ? "保存中..." : "保存 AI 配置"}
      </button>
    </form>
  );
}

function StoryCreator({
  token,
  onCreated,
  onError,
  setLoading
}: {
  token: string;
  onCreated: (story: Story) => void;
  onError: (message: string) => void;
  setLoading: (loading: boolean) => void;
}) {
  const [language, setLanguage] = useState("bilingual");
  const [topic, setTopic] = useState("懂礼貌的小兔子");
  const [extraPrompt, setExtraPrompt] = useState("");
  const [busy, setBusy] = useState(false);
  const [randomizingTopic, setRandomizingTopic] = useState(false);
  const suggestions = useMemo(() => [
    "爱洗手的小花猫",
    "愿意分享玩具的小熊",
    "认真洗水果的小猪",
    "知错就改的小象"
  ], []);

  async function randomizeTopic() {
    if (randomizingTopic) return;
    setRandomizingTopic(true);
    let nextTopic = "";
    try {
      const generated = await withTimeout(api.randomStoryTopic(token), 12000);
      if (generated.topic.trim()) {
        nextTopic = generated.topic.trim();
      }
    } catch {
      nextTopic = pickLocalTopic(topic);
    } finally {
      if (!nextTopic) {
        nextTopic = pickLocalTopic(topic);
      }
      setTopic(nextTopic);
      setRandomizingTopic(false);
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setLoading(true);
    try {
      const story = await api.createStory(token, {
        language,
        topic,
        extra_prompt: extraPrompt
      });
      onCreated(story);
      setExtraPrompt("");
    } catch (err) {
      onError(getErrorMessage(err, "故事生成失败，请稍后再试"));
    } finally {
      setBusy(false);
      setLoading(false);
    }
  }

  return (
    <form className="creator" onSubmit={submit}>
      <div className="creator-title">
        <span><Plus size={18} /></span>
        <h2>生成新故事</h2>
      </div>

      <label>
        语言
        <div className="select-shell">
          <select value={language} onChange={(event) => setLanguage(event.target.value)} aria-label="选择故事语言">
            {languages.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
          </select>
          <ChevronDown size={18} />
        </div>
      </label>

      <label>
        故事主题
        <div className="topic-row">
          <input value={topic} onChange={(event) => setTopic(event.target.value)} required />
          <button
            className="icon-only soft-action"
            type="button"
            onClick={randomizeTopic}
            title="优先用 AI 随机生成胎教主题"
            disabled={randomizingTopic}
          >
            {randomizingTopic ? <LoaderCircle className="spin" size={18} /> : <Shuffle size={18} />}
          </button>
        </div>
      </label>

      <div className="chips">
        {suggestions.map((item) => (
          <button key={item} type="button" onClick={() => setTopic(item)}>{item}</button>
        ))}
      </div>

      <label>
        本次补充提示词
        <textarea
          value={extraPrompt}
          onChange={(event) => setExtraPrompt(event.target.value)}
          placeholder="例如：加入数字 1 到 5，语气更轻柔；或写“控制在 300 字左右”。"
          rows={4}
        />
      </label>

      <button className="primary-button" disabled={busy}>
        {busy ? <LoaderCircle className="spin" size={18} /> : <Sparkles size={18} />}
        {busy ? "正在生成..." : "生成故事"}
      </button>
    </form>
  );
}

function StoryList({
  stories,
  selectedId,
  loading,
  deletingId,
  onSelect,
  onDelete
}: {
  stories: StorySummary[];
  selectedId?: number;
  loading: boolean;
  deletingId: number | null;
  onSelect: (id: number) => void;
  onDelete: (id: number) => void;
}) {
  if (loading && !stories.length) {
    return (
      <div className="empty-list">
        <LoaderCircle className="spin" size={28} />
        <p>故事列表加载中...</p>
      </div>
    );
  }

  if (!stories.length) {
    return (
      <div className="empty-list">
        <BookOpen size={28} />
        <p>还没有故事，先生成一个轻轻的开场。</p>
      </div>
    );
  }

  return (
    <div className="story-list">
      {loading && <p className="inline-loading"><LoaderCircle className="spin" size={16} /> 正在刷新故事列表...</p>}
      {stories.map((story) => (
        <article className={selectedId === story.id ? "story-item active" : "story-item"} key={story.id}>
          <button className="story-select" type="button" onClick={() => onSelect(story.id)} disabled={deletingId === story.id}>
            <span className="story-item-title">{story.title}</span>
            <span className="story-item-meta">
              {story.language} · {new Date(story.created_at).toLocaleDateString()}
            </span>
          </button>
          <span className={story.is_read ? "read-badge done" : "read-badge"}>
            {story.is_read ? <CheckCircle2 size={15} /> : <Sun size={15} />}
            {story.is_read ? "已读" : "未读"}
          </span>
          <button
            className="delete-button"
            title={deletingId === story.id ? "删除中" : "删除故事"}
            type="button"
            onClick={() => onDelete(story.id)}
            disabled={deletingId === story.id}
          >
            {deletingId === story.id ? <LoaderCircle className="spin" size={17} /> : <Trash2 size={17} />}
          </button>
        </article>
      ))}
    </div>
  );
}

function StoryReader({
  story,
  loading,
  markingRead,
  onRead
}: {
  story: Story | null;
  loading: boolean;
  markingRead: boolean;
  onRead: (id: number) => Promise<void>;
}) {
  const readerRef = useRef<HTMLElement | null>(null);
  const markedRef = useRef<number | null>(null);
  const [showBackTop, setShowBackTop] = useState(false);

  useEffect(() => {
    markedRef.current = null;
    setShowBackTop(false);
    readerRef.current?.scrollTo({ top: 0 });
  }, [story?.id]);

  useEffect(() => {
    if (!story) return;
    const activeStory = story;

    function updateWindowBackTop() {
      const doc = document.documentElement;
      const scrollTop = window.scrollY || doc.scrollTop;
      const isLongPage = doc.scrollHeight > window.innerHeight + 320;
      if (isLongPage) {
        setShowBackTop(scrollTop + window.innerHeight >= doc.scrollHeight - 260);
      }
      if (
        isLongPage &&
        !activeStory.is_read &&
        markedRef.current !== activeStory.id &&
        scrollTop + window.innerHeight >= doc.scrollHeight - 12
      ) {
        markedRef.current = activeStory.id;
        void onRead(activeStory.id);
      }
    }

    window.addEventListener("scroll", updateWindowBackTop, { passive: true });
    window.addEventListener("resize", updateWindowBackTop);
    updateWindowBackTop();
    return () => {
      window.removeEventListener("scroll", updateWindowBackTop);
      window.removeEventListener("resize", updateWindowBackTop);
    };
  }, [story, onRead]);

  function handleScroll() {
    const node = readerRef.current;
    if (!node || !story) return;
    const canScroll = node.scrollHeight > node.clientHeight + 24;
    const nearBottom = node.scrollTop + node.clientHeight >= node.scrollHeight - 220;
    setShowBackTop(canScroll && nearBottom);
    if (story.is_read || markedRef.current === story.id) return;
    const reachedBottom = node.scrollTop + node.clientHeight >= node.scrollHeight - 12;
    if (reachedBottom) {
      markedRef.current = story.id;
      void onRead(story.id);
    }
  }

  function scrollBackToTop() {
    readerRef.current?.scrollTo({ top: 0, behavior: "smooth" });
    window.scrollTo({ top: 0, behavior: "smooth" });
    setShowBackTop(false);
  }

  if (loading) {
    return <section className="reader loading"><LoaderCircle className="spin" size={24} /> 故事正在展开...</section>;
  }

  if (!story) {
    return (
      <section className="reader placeholder">
        <div className="soft-book">
          <BookOpen size={42} />
        </div>
        <h2>选择或生成一个故事</h2>
        <p>故事会保存在当前用户的列表中。滚动到故事底部后，会自动标记为已读。</p>
      </section>
    );
  }

  return (
    <section className="reader" ref={readerRef} onScroll={handleScroll}>
      <div className="reader-header">
        <div>
          <p className="eyebrow">{story.language} · {story.topic}</p>
          <h2>{story.title}</h2>
        </div>
        <span className={story.is_read ? "read-badge done" : "read-badge"}>
          {markingRead ? "标记中..." : story.is_read ? "已读" : "读到末尾后标记"}
        </span>
      </div>
      <StoryIllustration story={story} />
      <article className="story-content">
        {story.content.split("\n").filter(Boolean).map((paragraph, index) => (
          <p key={`${story.id}-${index}`}>{paragraph}</p>
        ))}
      </article>
      {showBackTop && (
        <button className="back-top-button" type="button" onClick={scrollBackToTop} aria-label="回到顶部" title="回到顶部">
          <ArrowUp size={20} />
        </button>
      )}
    </section>
  );
}

function Toast({
  message,
  type = "info",
  onClose
}: {
  message: string;
  type?: "info" | "error";
  onClose: () => void;
}) {
  useEffect(() => {
    if (!message) return;
    const timer = window.setTimeout(onClose, 3200);
    return () => window.clearTimeout(timer);
  }, [message, onClose]);

  if (!message) return null;

  return (
    <div className={`toast ${type}`} role={type === "error" ? "alert" : "status"}>
      <span>{message}</span>
      <button type="button" onClick={onClose} aria-label="关闭提示" title="关闭提示">
        <X size={14} />
      </button>
    </div>
  );
}

function StoryIllustration({ story }: { story: Story }) {
  const scene = getIllustrationScene(`${story.title} ${story.topic}`);

  return (
    <figure className={`story-illustration ${scene.kind}`} aria-label={`${story.title} 插图`}>
      <svg viewBox="0 0 760 300" role="img">
        <defs>
          <linearGradient id={`sky-${story.id}`} x1="0" x2="1" y1="0" y2="1">
            <stop offset="0%" stopColor={scene.skyStart} />
            <stop offset="100%" stopColor={scene.skyEnd} />
          </linearGradient>
          <filter id={`soft-${story.id}`} x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="12" stdDeviation="10" floodColor="#7a5d50" floodOpacity="0.16" />
          </filter>
        </defs>
        <rect width="760" height="300" rx="18" fill={`url(#sky-${story.id})`} />
        <circle cx="636" cy="62" r="32" fill="#fff4c7" opacity="0.95" />
        <circle cx="108" cy="74" r="18" fill="#ffffff" opacity="0.72" />
        <circle cx="132" cy="72" r="24" fill="#ffffff" opacity="0.72" />
        <circle cx="162" cy="76" r="16" fill="#ffffff" opacity="0.72" />
        <path d="M0 232 C130 202 220 230 330 210 C460 187 570 218 760 190 L760 300 L0 300 Z" fill={scene.ground} />
        <path d="M72 230 C104 184 154 188 178 230 Z" fill="#8ebf75" opacity="0.78" />
        <path d="M590 220 C622 170 682 176 712 220 Z" fill="#8ebf75" opacity="0.62" />
        <g filter={`url(#soft-${story.id})`}>
          <StoryAnimal scene={scene.kind} />
          <StoryProp scene={scene.kind} />
        </g>
        <text x="42" y="268" fill="#4e3b36" fontSize="22" fontWeight="800">{scene.caption}</text>
      </svg>
    </figure>
  );
}

function StoryAnimal({ scene }: { scene: string }) {
  const color = scene === "bear" ? "#b9865f" : scene === "cat" ? "#f4a6b7" : scene === "elephant" ? "#9db7c6" : "#f1c28b";
  const earColor = scene === "elephant" ? "#b9ced8" : color;

  return (
    <g>
      <ellipse cx="318" cy="194" rx="70" ry="58" fill={color} />
      <circle cx="318" cy="130" r="52" fill={color} />
      <circle cx="278" cy="94" r="22" fill={earColor} />
      <circle cx="358" cy="94" r="22" fill={earColor} />
      {scene === "rabbit" && (
        <>
          <ellipse cx="288" cy="76" rx="18" ry="46" fill="#f1c28b" />
          <ellipse cx="348" cy="76" rx="18" ry="46" fill="#f1c28b" />
        </>
      )}
      {scene === "elephant" && <path d="M344 144 C396 156 390 210 350 205" fill="none" stroke="#9db7c6" strokeWidth="22" strokeLinecap="round" />}
      <circle cx="300" cy="126" r="5" fill="#2f2522" />
      <circle cx="338" cy="126" r="5" fill="#2f2522" />
      <path d="M304 150 Q318 162 334 150" fill="none" stroke="#604a42" strokeWidth="5" strokeLinecap="round" />
      <path d="M258 185 Q214 206 202 236" fill="none" stroke={color} strokeWidth="16" strokeLinecap="round" />
      <path d="M376 184 Q424 202 444 232" fill="none" stroke={color} strokeWidth="16" strokeLinecap="round" />
      <ellipse cx="286" cy="249" rx="22" ry="12" fill="#755547" opacity="0.25" />
      <ellipse cx="352" cy="249" rx="22" ry="12" fill="#755547" opacity="0.25" />
    </g>
  );
}

function StoryProp({ scene }: { scene: string }) {
  if (scene === "wash") {
    return (
      <g>
        <rect x="452" y="174" width="120" height="70" rx="20" fill="#8fd2df" />
        <path d="M478 170 C478 136 538 136 538 170" fill="none" stroke="#5daebe" strokeWidth="12" strokeLinecap="round" />
        <circle cx="494" cy="154" r="8" fill="#ffffff" />
        <circle cx="525" cy="140" r="6" fill="#ffffff" />
        <circle cx="552" cy="156" r="5" fill="#ffffff" />
      </g>
    );
  }
  if (scene === "share") {
    return (
      <g>
        <rect x="462" y="170" width="86" height="62" rx="10" fill="#f5cf62" />
        <path d="M462 190 H548" stroke="#c88435" strokeWidth="8" />
        <circle cx="505" cy="160" r="18" fill="#e97b67" />
      </g>
    );
  }
  if (scene === "school") {
    return (
      <g>
        <rect x="458" y="150" width="112" height="88" rx="12" fill="#f1a76f" />
        <path d="M448 154 L514 100 L580 154 Z" fill="#d85f84" />
        <rect x="500" y="188" width="30" height="50" rx="6" fill="#fff6df" />
      </g>
    );
  }
  if (scene === "chores") {
    return (
      <g>
        <rect x="460" y="158" width="110" height="78" rx="12" fill="#f5e0b8" />
        <path d="M482 182 H548 M482 204 H548" stroke="#bd8d62" strokeWidth="8" strokeLinecap="round" />
        <path d="M594 136 L614 238" stroke="#7b665b" strokeWidth="8" strokeLinecap="round" />
        <path d="M586 238 H628" stroke="#d85f84" strokeWidth="12" strokeLinecap="round" />
      </g>
    );
  }
  return (
    <g>
      <path d="M478 162 C520 132 574 150 582 196 C590 242 520 254 474 228 C444 210 448 180 478 162 Z" fill="#d7ed9f" />
      <circle cx="512" cy="184" r="20" fill="#e8645f" />
      <circle cx="548" cy="202" r="18" fill="#f0b14b" />
      <path d="M528 154 C538 138 556 138 566 152" fill="none" stroke="#6f8c54" strokeWidth="7" strokeLinecap="round" />
    </g>
  );
}

function getIllustrationScene(text: string) {
  if (/洗手|水果|干净|clean|wash/i.test(text)) {
    return { kind: "wash", caption: "干干净净，安心长大", skyStart: "#e8fbff", skyEnd: "#fff6e8", ground: "#cbe8bb" };
  }
  if (/分享|玩具|谢谢|礼貌|please|thank/i.test(text)) {
    return { kind: "share", caption: "轻轻说话，学会分享", skyStart: "#fff2f6", skyEnd: "#fff8dc", ground: "#d9efbd" };
  }
  if (/上学|幼儿园|诚实|school|honest/i.test(text)) {
    return { kind: "school", caption: "诚实勇敢，快乐上学", skyStart: "#e8f4ff", skyEnd: "#fff1d7", ground: "#c8e5c0" };
  }
  if (/整理|劳动|勤劳|收玩具|帮妈妈|chores|tidy/i.test(text)) {
    return { kind: "chores", caption: "小小双手，也会帮忙", skyStart: "#f3fff1", skyEnd: "#fff2e2", ground: "#d2e8b5" };
  }
  if (/小象|elephant/i.test(text)) {
    return { kind: "elephant", caption: "知错就改，心里亮亮", skyStart: "#edf7ff", skyEnd: "#fff4ef", ground: "#cde4bf" };
  }
  if (/小熊|bear/i.test(text)) {
    return { kind: "bear", caption: "温柔小熊，学会好习惯", skyStart: "#fff4e8", skyEnd: "#fff8ce", ground: "#d9e9b0" };
  }
  if (/小猫|cat/i.test(text)) {
    return { kind: "cat", caption: "小花猫记住好习惯", skyStart: "#fff0f5", skyEnd: "#f0fbff", ground: "#d6ecc4" };
  }
  return { kind: "rabbit", caption: "小小故事，暖暖道理", skyStart: "#fff1f6", skyEnd: "#eefaff", ground: "#d8edbb" };
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
