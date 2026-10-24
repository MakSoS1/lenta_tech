import { useEffect, useState } from "react";
import {
  ArrowUpRight,
  SlidersHorizontal,
  Sparkles,
  CornerDownLeft,
  LockKeyhole,
} from "lucide-react";
import type { Capabilities, Intent, TripState } from "../types";
import { compactPatch, parseChildrenAges } from "../behavior";
interface Props {
  trip: TripState | null;
  capabilities: Capabilities | null;
  busy: boolean;
  onSend: (message: string, patch?: Record<string, unknown>) => void;
}
export default function TripInput({ trip, capabilities, busy, onSend }: Props) {
  const [message, setMessage] = useState("");
  const [draft, setDraft] = useState<Record<string, string | boolean>>({});
  const intent = trip?.intent;
  useEffect(() => {
    if (intent)
      setDraft(
        Object.fromEntries(
          Object.entries(intent).map(([key, value]) => [
            key,
            typeof value === "boolean"
              ? value
              : Array.isArray(value)
                ? value.join(", ")
                : value == null
                  ? ""
                  : String(value),
          ]),
        ),
      );
  }, [intent]);
  function edit(key: string, value: string | boolean) {
    setDraft((current) => ({ ...current, [key]: value }));
  }
  function apply() {
    if (!intent) return;
    const number = (key: string, nullable = false) =>
      draft[key] === "" && nullable ? null : Number(draft[key]);
    const next: Partial<Intent> = {
      origin: String(draft.origin) || null,
      destinations: String(draft.destinations)
        .split(",")
        .map((v) => v.trim())
        .filter(Boolean),
      departure_date: String(draft.departure_date) || null,
      ...(intent.return_by != null || draft.return_by
        ? { return_by: String(draft.return_by) || null }
        : {}),
      nights: Number(draft.nights),
      adults: Number(draft.adults),
      children_count: Number(draft.children_count),
      children_ages: parseChildrenAges(String(draft.children_ages)),
      pet_kg: number("pet_kg", true),
      ...(intent.pet_requested ||
      intent.pet_kg != null ||
      Number(draft.pet_kg) > 0
        ? { pet_requested: true }
        : {}),
      budget_rub: number("budget_rub", true),
      max_travel_hours: number("max_travel_hours", true),
      transport: String(draft.transport),
      meal: String(draft.meal),
      hotel_preference: String(draft.hotel_preference),
      refundable: !!draft.refundable,
      warm: !!draft.warm,
      lock_transport: !!draft.lock_transport,
      rooms: Number(draft.rooms),
    };
    onSend("Обновить условия поездки", compactPatch(intent, next));
  }
  const textInput = (
    key: string,
    label: string,
    props: Record<string, unknown> = {},
  ) => (
    <label className="field" key={key}>
      <span>{label}</span>
      <input
        aria-label={label}
        value={String(draft[key] ?? "")}
        onChange={(e) => edit(key, e.target.value)}
        {...props}
      />
    </label>
  );
  const select = (
    key: string,
    label: string,
    options: { id: string; name: string }[],
  ) => (
    <label className="field" key={key}>
      <span>{label}</span>
      <select
        aria-label={label}
        value={String(draft[key] ?? "")}
        onChange={(e) => edit(key, e.target.value)}
      >
        {options.map((item) => (
          <option value={item.id} key={item.id}>
            {item.name}
          </option>
        ))}
      </select>
    </label>
  );
  return (
    <section className="request-panel panel">
      <div className="section-eyebrow">
        <Sparkles size={15} /> ВАШ ЛИЧНЫЙ ТРЕВЕЛ-АГЕНТ
      </div>
      <h2>{trip ? "Продолжим собирать?" : "Расскажите о вашей поездке"}</h2>
      <p className="muted">
        Куда хочется, с кем едете и что важно. Остальное соберём вместе.
      </p>
      {trip && (
        <div className="conversation" aria-label="Диалог с агентом">
          {trip.messages.slice(-6).map((item, index) => (
            <div
              key={index}
              className={`message ${item.role === "user" ? "from-user" : "from-agent"}`}
            >
              <span>{item.role === "user" ? "Вы" : "О!Собрано"}</span>
              <p>{item.text}</p>
            </div>
          ))}
        </div>
      )}
      <form
        className="message-form"
        onSubmit={(e) => {
          e.preventDefault();
          if (message.trim()) {
            onSend(message);
            setMessage("");
          }
        }}
      >
        <label className="sr-only" htmlFor="trip-message">
          Ваш запрос
        </label>
        <textarea
          maxLength={4000}
          id="trip-message"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="Хочу к морю в ноябре, вдвоём, на 5 ночей. Из Москвы, до 180 000 ₽…"
          rows={4}
          disabled={busy}
        />
        <div className="composer-bottom">
          <span>
            <CornerDownLeft size={13} /> Можно своими словами
          </span>
          <button
            className="icon-button"
            aria-label={trip ? "Отправить сообщение" : "Собрать поездку"}
            disabled={busy || !message.trim()}
            type="submit"
          >
            <ArrowUpRight size={23} />
          </button>
        </div>
      </form>
      {!trip && (
        <div className="example">
          <span>Попробуйте, например</span>
          <button
            className="example-button"
            disabled={busy}
            onClick={() =>
              onSend(
                "Из Москвы в Сочи 15 ноября 2026 на 5 ночей, двое взрослых, бюджет 180000 рублей",
              )
            }
          >
            К морю на несколько дней <ArrowUpRight size={14} />
          </button>
        </div>
      )}
      {trip && (
        <form
          className="conditions"
          onSubmit={(e) => {
            e.preventDefault();
            apply();
          }}
        >
          <div className="section-line">
            <h3>
              <SlidersHorizontal size={16} /> Условия поездки
            </h3>
            <span className="version" data-testid="trip-version">
              v{trip.version}
            </span>
          </div>
          <div className="fields-grid">
            {select("origin", "Откуда", [
              { id: "", name: "Уточните город" },
              ...(capabilities?.catalog.origins ?? []),
            ])}
            {select("destinations", "Куда", [
              { id: "", name: "Подобрать направление" },
              ...(capabilities?.catalog.destinations ?? []),
            ])}
            {textInput("departure_date", "Дата отправления", {
              type: "date",
              min: capabilities?.catalog.date_from,
              max: capabilities?.catalog.date_to,
            })}
            {textInput("nights", "Ночей", {
              type: "number",
              min: 2,
              max: 14,
              required: true,
            })}
            {textInput("adults", "Взрослых", {
              type: "number",
              min: 1,
              max: 8,
              required: true,
            })}
            {textInput("budget_rub", "Бюджет, ₽", {
              type: "number",
              min: 1000,
              max: 5000000,
              step: 1000,
              placeholder: "Без ограничения",
            })}
          </div>
          {intent?.pet_requested && intent.pet_kg == null && (
            <div className="unresolved-pet">
              <strong>Уточните вес питомца</strong>
              <p>
                Питомец учтён в запросе. Укажите его вес в дополнительных
                пожеланиях, чтобы проверить все тарифы.
              </p>
            </div>
          )}
          <details className="advanced">
            <summary>Дети, питомец и другие пожелания</summary>
            <div className="fields-grid">
              {textInput("return_by", "Вернуться не позже", {
                type: "date",
                min: capabilities?.catalog.date_from,
                max: capabilities?.catalog.date_to,
              })}
              {textInput("children_count", "Детей", {
                type: "number",
                min: 0,
                max: 4,
              })}
              {textInput("children_ages", "Возраст детей", {
                placeholder: "7, 12; пусто — неизвестно",
              })}
              {textInput("pet_kg", "Питомец, кг", {
                type: "number",
                min: 0.1,
                max: 50,
                step: 0.1,
                placeholder: "Вес не указан",
              })}
              {textInput("rooms", "Номеров", {
                type: "number",
                min: 1,
                max: 4,
              })}
              {textInput("max_travel_hours", "В пути не больше, ч", {
                type: "number",
                min: 0.5,
                step: 0.5,
                placeholder: "Не ограничено",
              })}
              {select("transport", "Транспорт", [
                { id: "any", name: "Любой" },
                { id: "flight", name: "Самолёт" },
                { id: "train", name: "Поезд" },
              ])}
              {select("meal", "Питание", [
                { id: "any", name: "Любое" },
                { id: "breakfast", name: "Завтрак" },
                { id: "all_inclusive", name: "Всё включено" },
              ])}
              {select("hotel_preference", "Расположение", [
                { id: "any", name: "Не важно" },
                { id: "center", name: "В центре" },
                { id: "beach", name: "У пляжа" },
              ])}
            </div>
            <div className="checks">
              {[
                ["refundable", "Возвратные тарифы"],
                ["warm", "Хочется в тепло"],
                ["lock_transport", "Сохранить выбранный транспорт"],
              ].map(([key, label]) => (
                <label className="checkbox" key={key}>
                  <input
                    type="checkbox"
                    checked={!!draft[key]}
                    onChange={(e) => edit(key, e.target.checked)}
                  />
                  {label}
                </label>
              ))}
            </div>
            <p className="fine">
              Возраст каждого ребёнка нужен для расчёта. Пустое поле означает,
              что возраст пока неизвестен.
            </p>
          </details>
          {(intent?.pet_requested || intent?.pet_kg != null) && (
            <button
              className="text-button no-pet"
              type="button"
              disabled={busy}
              onClick={() =>
                onSend("Еду без питомца", {
                  pet_requested: false,
                  pet_kg: null,
                })
              }
            >
              Без питомца — убрать из условий
            </button>
          )}
          <button
            className="button secondary full"
            disabled={busy}
            type="submit"
          >
            Применить условия <ArrowUpRight size={16} />
          </button>
          <button
            className="text-button shift-button"
            disabled={busy || !intent?.departure_date}
            type="button"
            onClick={() =>
              onSend("Сдвинуть поездку на два дня", { shift_days: 2 })
            }
          >
            А если на 2 дня позже?
          </button>
          {trip.locked_component_ids.length > 0 && (
            <p className="fine">
              <LockKeyhole size={13} /> Транспорт зафиксирован. Если условия
              несовместимы, агент попросит снять ограничение.
            </p>
          )}
        </form>
      )}
    </section>
  );
}
