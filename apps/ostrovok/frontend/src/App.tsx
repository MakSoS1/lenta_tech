import { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowDown,
  ArrowUpRight,
  History,
  Plus,
  Route,
  Sparkles,
  X,
  Check,
  Compass,
  Plane,
  ShieldCheck,
  LoaderCircle,
  ChevronRight,
  Terminal,
  Globe2,
  CircleHelp,
} from "lucide-react";
import type { Capabilities, HistoryItem, TripState } from "./types";
import { api, ApiError } from "./api";
import TripInput from "./components/TripInput";
import TripComparison, { Validation } from "./components/TripComparison";
import TripTimeline from "./components/TripTimeline";
import PlanChanges from "./components/PlanChanges";
import Checkout from "./components/Checkout";
const STORAGE_KEY = "ostrovok_trip_id";
export default function App() {
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [trip, setTrip] = useState<TripState | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [preferences, setPreferences] = useState<Record<string, unknown>>({});
  const [remember, setRemember] = useState(false);
  const [notice, setNotice] = useState("");
  const [service, setService] = useState<string | null>(null);
  const [streamEvents, setStreamEvents] = useState<string[]>([]);
  const abort = useRef<AbortController | null>(null);
  const lastOrderKey = useRef<{ quote: string; key: string } | null>(null);
  const adopt = useCallback((state: TripState) => {
    setTrip(state);
    localStorage.setItem(STORAGE_KEY, state.trip_id);
    setService(state.service_requests?.find((request) => request.kind === "early_checkin")?.message ?? null);
  }, []);
  useEffect(() => {
    let active = true;
    async function load() {
      const [caps, items, prefs] = await Promise.allSettled([
        api.capabilities(),
        api.history(),
        api.preferences(),
      ]);
      if (!active) return;
      if (caps.status === "fulfilled") setCapabilities(caps.value);
      else
        setError(
          "Не удалось подключиться к агенту. Проверьте подключение и обновите страницу.",
        );
      if (items.status === "fulfilled") setHistory(items.value.trips);
      if (prefs.status === "fulfilled") setPreferences(prefs.value.preferences);
      const id = localStorage.getItem(STORAGE_KEY);
      if (id)
        try {
          const restored = await api.trip(id);
          if (active) adopt(restored);
        } catch {
          if (active) {
            localStorage.removeItem(STORAGE_KEY);
            setNotice(
              "Эта поездка недоступна в текущей сессии. Начните новую или выберите поездку из истории.",
            );
          }
        }
      if (active) setLoading(false);
    }
    void load();
    return () => {
      active = false;
    };
  }, [adopt]);
  useEffect(() => {
    if (!trip?.trip_id) return;
    setStreamEvents([]);
    const stream = new EventSource(
      `/api/trips/${encodeURIComponent(trip.trip_id)}/events`,
    );
    const receive = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        const detail = data.detail ?? data.message ?? data.summary;
        if (typeof detail === "string")
          setStreamEvents((old) => [...old, detail].slice(-12));
      } catch {
        /* Only render actual structured server events. */
      }
    };
    stream.onmessage = receive;
    stream.addEventListener("done", () => stream.close());
    ["action", "trace", "state", "tool"].forEach((name) =>
      stream.addEventListener(name, receive as EventListener),
    );
    return () => stream.close();
  }, [trip?.trip_id, trip?.version]);
  async function refreshHistory() {
    try {
      setHistory((await api.history()).trips);
    } catch {
      /* Existing state remains usable when history is unavailable. */
    }
  }
  async function run(action: (signal: AbortSignal) => Promise<TripState>) {
    setBusy(true);
    setError("");
    setNotice("");
    const controller = new AbortController();
    abort.current = controller;
    try {
      adopt(await action(controller.signal));
      await refreshHistory();
    } catch (problem) {
      if (problem instanceof DOMException && problem.name === "AbortError") {
        setNotice(
          "Ожидание отменено. Сервер мог закончить действие; обновите поездку, чтобы получить актуальное состояние.",
        );
      } else {
        setError(
          problem instanceof Error
            ? problem.message
            : "Не получилось выполнить действие. Попробуйте ещё раз.",
        );
        if (problem instanceof ApiError && problem.status === 409 && trip) {
          try {
            adopt(await api.trip(trip.trip_id));
          } catch {
            /* The original error remains visible. */
          }
        }
      }
    } finally {
      setBusy(false);
      abort.current = null;
    }
  }
  function send(message: string, patch?: Record<string, unknown>) {
    void run((signal) =>
      trip
        ? api.mutate(
            trip.trip_id,
            "messages",
            { message, patch, expected_version: trip.version },
            signal,
          )
        : api.create(message, signal),
    );
  }
  function mutate(
    path: string,
    body: Record<string, unknown>,
    headers?: Record<string, string>,
  ) {
    if (trip)
      void run((signal) =>
        api.mutate(
          trip.trip_id,
          path,
          { expected_version: trip.version, ...body },
          signal,
          headers,
        ),
      );
  }
  function confirmOrder() {
    if (!trip?.quote) return;
    if (lastOrderKey.current?.quote !== trip.quote.quote_id)
      lastOrderKey.current = {
        quote: trip.quote.quote_id,
        key: crypto.randomUUID(),
      };
    mutate(
      "demo-orders",
      {
        quote_id: trip.quote.quote_id,
        confirmed: true,
        total_minor: trip.quote.total_minor,
      },
      { "Idempotency-Key": lastOrderKey.current.key },
    );
  }
  async function preferenceAction(remove = false) {
    setBusy(true);
    setError("");
    try {
      const value = remove
        ? await api.deletePreferences()
        : await api.savePreferences({
            meal: trip?.intent.meal,
            refundable: trip?.intent.refundable,
            hotel_preference: trip?.intent.hotel_preference,
          });
      setPreferences(value.preferences);
      setRemember(false);
      setNotice(
        remove
          ? "Сохранённые предпочтения удалены."
          : "Питание, возврат и расположение сохранены с вашего согласия.",
      );
    } catch (problem) {
      setError(
        problem instanceof Error
          ? problem.message
          : "Не удалось сохранить предпочтения.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function requestService() {
    if (!trip) return;
    setBusy(true);
    try {
      const result = await api.service(trip.trip_id);
      setService(result.message);
    } catch (problem) {
      setError(
        problem instanceof Error
          ? problem.message
          : "Не удалось отправить запрос.",
      );
    } finally {
      setBusy(false);
    }
  }
  const selected =
    trip?.order?.plan ??
    trip?.plans.find((plan) => plan.plan_id === trip.selected_plan_id);
  return (
    <div className="app-shell">
      <header className="site-header">
        <a
          className="brand"
          href="/"
          onClick={(e) => {
            e.preventDefault();
            window.scrollTo({ top: 0, behavior: "smooth" });
          }}
          aria-label="О!Собрано — наверх"
        >
          <span className="brand-mark">
            О<span>!</span>
          </span>
          <span>
            Собрано<span className="brand-by">by ostrovok</span>
          </span>
        </a>
        <div className="header-actions">
          <span className="header-note">
            <span /> Поездки с заботой о деталях
          </span>
          <button
            className="header-button"
            disabled={busy}
            onClick={() => {
              setHistoryOpen((v) => !v);
              void refreshHistory();
            }}
            aria-expanded={historyOpen}
          >
            <History size={17} />
            <span>Мои поездки</span>
          </button>
          {trip && (
            <button
              className="button small secondary"
              disabled={busy}
              onClick={() => {
                setTrip(null);
                localStorage.removeItem(STORAGE_KEY);
                setError("");
                setNotice("");
                setService(null);
              }}
            >
              <Plus size={16} /> Новая поездка
            </button>
          )}
        </div>
      </header>
      {historyOpen && (
        <section className="history-drawer panel" aria-label="История поездок">
          <div className="section-line">
            <h2>Мои поездки</h2>
            <button
              className="icon-button plain"
              onClick={() => setHistoryOpen(false)}
              aria-label="Закрыть историю"
            >
              <X size={20} />
            </button>
          </div>
          {history.length ? (
            history.map((item) => (
              <button
                className="history-item"
                key={item.trip_id}
                disabled={busy}
                onClick={() => {
                  setHistoryOpen(false);
                  void run((signal) => api.trip(item.trip_id, signal));
                }}
              >
                <span>
                  <strong>{item.title}</strong>
                  <small>
                    {new Date(item.updated_at).toLocaleDateString("ru-RU")} · v
                    {item.version} ·{" "}
                    {item.status === "ordered" ? "Демозаказ" : "Планирование"}
                  </small>
                </span>
                <ChevronRight size={18} />
              </button>
            ))
          ) : (
            <p className="muted">
              Здесь появятся поездки, собранные в этой сессии браузера.
            </p>
          )}
        </section>
      )}
      <main>
        <section className={`hero ${trip ? "compact-hero" : ""}`}>
          <div className="hero-copy">
            <div className="hero-eyebrow">
              <span className="pill-dot" /> МЕНЬШЕ ВКЛАДОК. БОЛЬШЕ ПУТЕШЕСТВИЙ.
            </div>
            <h1>
              Поездка, которая
              <br />
              <em>складывается.</em>
            </h1>
            <p>
              Дорога, отель и трансферы — в одном плане.
              <br />
              Скажите, чего хочется. Мы свяжем все детали.
            </p>
            {!trip && (
              <div className="hero-bottom">
                <span className="hero-circle">
                  <ArrowDown size={18} />
                </span>
                <span>Начните с одной идеи</span>
              </div>
            )}
          </div>
          <div className="hero-visual" aria-hidden="true">
            <div className="orbit orbit-one" />
            <div className="orbit orbit-two" />
            <span className="visual-spark">✳</span>
            <div className="travel-ticket">
              <div className="ticket-top">
                <span>
                  ВАШ СЛЕДУЮЩИЙ
                  <br />
                  ХОРОШИЙ ПЛАН
                </span>
                <Compass size={27} />
              </div>
              <div className="ticket-route">
                <span>МЕЧТА</span>
                <Plane size={25} />
                <span>ПОЕЗДКА</span>
              </div>
              <div className="ticket-line" />
              <div className="ticket-bottom">
                <span>
                  ВСЁ УЖЕ
                  <br />
                  <strong>СОБРАНО</strong>
                </span>
                <div className="ticket-barcode" />
              </div>
            </div>
            <div className="floating-note">
              <Check size={16} />
              <span>Каждая деталь на месте</span>
            </div>
            <span className="visual-coordinate">
              43°35′ N · ВАШЕ НОВОЕ МЕСТО
            </span>
          </div>
        </section>
        <div className="mode-strip">
          <div>
            <ShieldCheck size={16} />
            <strong>Честное демо</strong>
            <span>Цены и оформление демонстрационные</span>
          </div>
          <span className="mode-indicator">
            {trip
              ? trip.llm.used
                ? "AI подключён"
                : "Ограниченный режим без LLM"
              : capabilities?.llm.mode === "offline"
                ? "Ограниченный режим без LLM"
                : "Бесплатные модели OpenCode"}
          </span>
        </div>
        {error && (
          <div className="alert error" role="alert">
            <CircleHelp size={19} />
            <p>{error}</p>
            <button
              className="icon-button plain"
              onClick={() => setError("")}
              aria-label="Закрыть ошибку"
            >
              <X size={17} />
            </button>
          </div>
        )}
        {notice && (
          <div className="alert notice" role="status">
            <Check size={18} />
            <p>{notice}</p>
          </div>
        )}
        {loading ? (
          <div className="loading">
            <LoaderCircle className="spin" size={25} /> Восстанавливаем ваше
            пространство…
          </div>
        ) : (
          <div className="workspace">
            <aside className="sidebar">
              <TripInput
                trip={trip}
                capabilities={capabilities}
                busy={busy}
                onSend={send}
              />
              {trip && (
                <section className="preferences panel">
                  <h3>Пожелания на будущее</h3>
                  <p className="fine">
                    Можно запомнить питание, расположение отеля и возможность
                    возврата.
                  </p>
                  <label className="checkbox">
                    <input
                      type="checkbox"
                      checked={remember}
                      onChange={(e) => setRemember(e.target.checked)}
                    />
                    Сохранить эти предпочтения
                  </label>
                  <div className="preference-actions">
                    <button
                      className="text-button"
                      disabled={!remember || busy}
                      onClick={() => void preferenceAction()}
                    >
                      Запомнить
                    </button>
                    {Object.keys(preferences).length > 0 && (
                      <button
                        className="text-button"
                        disabled={busy}
                        onClick={() => void preferenceAction(true)}
                      >
                        Удалить сохранённое
                      </button>
                    )}
                  </div>
                </section>
              )}
            </aside>
            <div className="results" aria-live="polite" aria-busy={busy}>
              {busy && (
                <div className="working">
                  <LoaderCircle className="spin" size={17} />
                  <span>Агент работает с вашим запросом…</span>
                  {abort.current && (
                    <button
                      onClick={() => abort.current?.abort()}
                      className="text-button"
                    >
                      Отменить ожидание
                    </button>
                  )}
                </div>
              )}
              {!trip ? (
                <EmptyState />
              ) : (
                <>
                  {trip.questions.length > 0 && (
                    <section className="clarifications panel">
                      <div className="section-eyebrow">ЧТОБЫ ВСЁ ПОДОШЛО</div>
                      <h2>Уточним пару деталей</h2>
                      {trip.questions.map((question) => (
                        <div className="question" key={question.key}>
                          <h3>{question.label}</h3>
                          <div className="suggestions">
                            {question.suggestions.map((suggestion) => (
                              <button
                                className="suggestion"
                                disabled={busy}
                                key={suggestion}
                                onClick={() => send(suggestion)}
                              >
                                {suggestion}
                                <ArrowUpRight size={13} />
                              </button>
                            ))}
                          </div>
                          {question.key === "unsupported" && (
                            <button
                              className="button secondary full"
                              style={{ marginTop: 12 }}
                              disabled={busy}
                              onClick={() =>
                                send("Сними неподдерживаемые ограничения")
                              }
                            >
                              Снять перечисленные неподдерживаемые ограничения
                            </button>
                          )}
                        </div>
                      ))}
                      <p className="fine">
                        Можно ответить сообщением или изменить условия слева.
                      </p>
                    </section>
                  )}
                  <PlanChanges delta={trip.delta} />
                  {trip.plans.length > 0 && (
                    <TripComparison
                      trip={trip}
                      busy={busy}
                      onSelect={(id) => mutate("selection", { plan_id: id })}
                    />
                  )}
                  {!trip.plans.length && !trip.questions.length && (
                    <section className="panel no-options">
                      <Compass size={34} />
                      <h2>
                        {trip.status === "needs_resolution"
                          ? "Условия нужно согласовать"
                          : "Пока не нашли подходящую поездку"}
                      </h2>
                      <p>
                        Попробуйте изменить даты, бюджет или ограничение на
                        транспорт. Ваши условия сохранены.
                      </p>
                    </section>
                  )}
                  {selected && (
                    <>
                      <TripTimeline plan={selected} />
                      <Validation plan={selected} />
                      {selected.weather && (
                        <Weather weather={selected.weather} />
                      )}
                      <Checkout
                        trip={trip}
                        plan={selected}
                        busy={busy}
                        onQuote={() => mutate("quote", {})}
                        onOrder={confirmOrder}
                        onService={() => void requestService()}
                        service={service}
                      />
                    </>
                  )}
                  <section className="transparency panel">
                    <h3>
                      <CircleHelp size={17} /> Что известно, а что уточняем
                    </h3>
                    {trip.assumptions.length > 0 && (
                      <div>
                        <h4>Рабочие допущения</h4>
                        <ul>
                          {trip.assumptions.map((text, index) => (
                            <li key={index}>{text}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {trip.warnings.length > 0 && (
                      <div>
                        <h4>Важно учесть</h4>
                        <ul>
                          {trip.warnings.map((text, index) => (
                            <li key={index}>{text}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    <p className="fine">
                      Цены и наличие взяты из демонстрационного каталога.
                      Пожелания к заселению требуют отдельного подтверждения.
                    </p>
                    {trip.llm.reason && (
                      <p className="fine">Режим обработки: {trip.llm.reason}</p>
                    )}
                    <p className="fine">
                      Модель: {trip.llm.model ?? "не использовалась"} · Отсчёт
                      дат:{" "}
                      {new Date(trip.reference_now).toLocaleString("ru-RU")} ·{" "}
                      {trip.origin_timezone}
                    </p>
                  </section>
                  <details className="trace panel">
                    <summary>
                      <Terminal size={17} />
                      <strong>Как агент собрал поездку</strong>
                      <span>{trip.action_trace.length} действий</span>
                    </summary>
                    <p className="fine">
                      Фактический журнал инструментов с сервера.
                    </p>
                    <ol>
                      {trip.action_trace.map((action, index) => (
                        <li key={`${action.tool}-${index}`}>
                          <span className="trace-number">
                            {String(index + 1).padStart(2, "0")}
                          </span>
                          <div>
                            <strong>{action.tool}</strong>
                            <p>{action.detail}</p>
                          </div>
                          <span className="trace-status">{action.status}</span>
                        </li>
                      ))}
                    </ol>
                    {streamEvents.length > 0 && (
                      <details className="stream-events">
                        <summary>События соединения</summary>
                        {streamEvents.map((event, index) => (
                          <p key={index}>{event}</p>
                        ))}
                      </details>
                    )}
                    <button
                      className="text-button"
                      disabled={busy}
                      onClick={() =>
                        void run((signal) => api.trip(trip.trip_id, signal))
                      }
                    >
                      Обновить с сервера
                    </button>
                  </details>
                </>
              )}
            </div>
          </div>
        )}
      </main>
      <footer>
        <a
          className="footer-brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            window.scrollTo({ top: 0, behavior: "smooth" });
          }}
        >
          О!Собрано
        </a>
        <p>Хорошее путешествие начинается с хорошего плана.</p>
        <span>Создано для демо · 2026</span>
      </footer>
    </div>
  );
}
function EmptyState() {
  return (
    <section className="empty-state">
      <div className="section-eyebrow">НЕ ПРОСТО НАЙТИ. СОБРАТЬ.</div>
      <h2>
        У хорошей поездки
        <br />
        все детали <em>дружат.</em>
      </h2>
      <p className="empty-description">
        Не нужно сверять рейсы с заселением и складывать цены. Агент делает это
        за вас — и показывает, как.
      </p>
      <div className="process-list">
        {[
          {
            icon: <Compass size={20} />,
            title: "Понимаем, что важно",
            text: "Состав группы, даты, бюджет и ваши «обязательно».",
          },
          {
            icon: <Route size={20} />,
            title: "Связываем детали",
            text: "Дорога, проживание и трансферы подходят друг к другу.",
          },
          {
            icon: <Sparkles size={20} />,
            title: "Находим ваш баланс",
            text: "Сравниваем варианты и честно объясняем компромиссы.",
          },
        ].map((step, index) => (
          <div className="process-item" key={step.title}>
            <span className="process-icon">{step.icon}</span>
            <div>
              <span className="process-number">0{index + 1}</span>
              <h3>{step.title}</h3>
              <p>{step.text}</p>
            </div>
          </div>
        ))}
      </div>
      <div className="empty-note">
        <ShieldCheck size={18} />
        <span>
          Итоговая цена — за всю поездку.
          <br />
          <strong>Подтверждение всегда остаётся за вами.</strong>
        </span>
      </div>
    </section>
  );
}
function Weather({ weather }: { weather: Record<string, unknown> }) {
  const fields = [
    ["temperature_mean_c", "Средняя температура, °C"],
    ["precipitation_mean_monthly_mm", "Осадки за месяц, мм"],
    ["period", "Период наблюдений"],
    ["sample_days", "Дней в выборке"],
  ];
  return (
    <section className="weather panel">
      <h3>
        <Globe2 size={17} /> Погода в это время года
      </h3>
      <p className="fine" style={{ marginTop: 10 }}>
        {String(weather.label ?? "Контекст погоды: тип данных не указан")}
      </p>
      <dl>
        {fields
          .filter(([key]) => weather[key] != null)
          .map(([key, label]) => (
            <div key={key}>
              <dt>{label}</dt>
              <dd>{String(weather[key])}</dd>
            </div>
          ))}
      </dl>
      {!!weather.source && (
        <p className="fine" style={{ marginTop: 12 }}>
          {String(weather.source)}
          {weather.license ? ` · ${String(weather.license)}` : ""}
        </p>
      )}
      {!!weather.attribution && (
        <p className="fine">{String(weather.attribution)}</p>
      )}
    </section>
  );
}
