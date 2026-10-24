import { useEffect, useState } from "react";
import {
  ArrowUpRight,
  Check,
  ShieldCheck,
  ReceiptText,
  CircleCheck,
} from "lucide-react";
import type { Plan, TripState } from "../types";
import { canConfirmOrder, formatMoney } from "../behavior";
import { componentNames, OfferIcon, SourceBadge } from "./TripComparison";
import { dateTime } from "./TripTimeline";
export default function Checkout({
  trip,
  plan,
  busy,
  onQuote,
  onOrder,
  onService,
  service,
}: {
  trip: TripState;
  plan: Plan;
  busy: boolean;
  onQuote: () => void;
  onOrder: () => void;
  onService: () => void;
  service: string | null;
}) {
  const [consent, setConsent] = useState(false);
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    setConsent(false);
  }, [trip.quote?.quote_id, trip.version]);
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);
  return (
    <section className="panel checkout">
      <div className="section-line">
        <h2>Вся поездка в одной корзине</h2>
        <ReceiptText size={20} />
      </div>
      <p className="muted">Для всей группы, с дорогой туда и обратно.</p>
      <div className="price-items">
        {plan.components.map((offer) => (
          <div className="price-item" key={offer.offer_id}>
            <div className="component-icon">
              <OfferIcon offer={offer} />
            </div>
            <div className="component-info">
              <h3>{componentNames[offer.kind]}</h3>
              <p>{offer.title}</p>
              <SourceBadge offer={offer} />
              <details className="offer-details">
                <summary>Условия и источник</summary>
                <dl>
                  {Object.entries(offer.details).map(([key, value]) => (
                    <div key={key}>
                      <dt>{detailLabel(key)}</dt>
                      <dd>{detailValue(key, value)}</dd>
                    </div>
                  ))}
                </dl>
                <p>
                  Данные: {dateTime(offer.source.observed_at)}. Действуют до{" "}
                  {dateTime(offer.expires_at)}.
                </p>
                {/^https:\/\//.test(offer.source.url) && (
                  <a href={offer.source.url} target="_blank" rel="noreferrer">
                    Открыть источник ↗
                  </a>
                )}
              </details>
            </div>
            <strong>{formatMoney(offer.total_minor)}</strong>
          </div>
        ))}
      </div>
      <div className="total-line">
        <div>
          <span>Итого за поездку</span>
          <small>Все три компонента включены</small>
        </div>
        <strong>
          {formatMoney(trip.quote?.total_minor ?? plan.total_minor)}
        </strong>
      </div>
      {trip.order ? (
        <div className="receipt" role="status">
          <span className="receipt-icon">
            <Check size={25} />
          </span>
          <div className="section-eyebrow">ДЕМОЗАКАЗ ПОДТВЕРЖДЁН</div>
          <h2>Поездка собрана!</h2>
          <p>
            Сумма: <strong>{formatMoney(trip.order.total_minor)}</strong>
          </p>
          <p className="order-number">
            Номер <span data-testid="order-id">{trip.order.order_id}</span>
          </p>
          <p className="fine">{dateTime(trip.order.created_at)}</p>
          <p className="fine">Бронирование и оплата имитируются</p>
          <button
            className="button secondary full"
            disabled={busy || !!service}
            onClick={onService}
          >
            {service ? (
              <>
                <CircleCheck size={16} /> Запрос сохранён
              </>
            ) : (
              "Запросить раннее заселение"
            )}
          </button>
          {service && <p className="fine">{service}</p>}
          <p className="fine">
            Демозапрос не гарантирует заселение и не отправляется в реальный
            отель.
          </p>
        </div>
      ) : (
        <>
          {!trip.quote ? (
            <button
              className="button primary full quote-button"
              disabled={busy || !plan.validation.passed}
              onClick={onQuote}
            >
              Проверить итоговую цену <ArrowUpRight size={17} />
            </button>
          ) : (
            <div className="quote-confirmation">
              <p className="quote-checked">
                <ShieldCheck size={17} /> Цена проверена до{" "}
                {dateTime(trip.quote.expires_at)}
              </p>
              <label className="checkbox consent">
                <input
                  type="checkbox"
                  checked={consent}
                  onChange={(e) => setConsent(e.target.checked)}
                  disabled={busy}
                />{" "}
                <span>
                  Я подтверждаю состав поездки и демонстрационную сумму
                </span>
              </label>
              <button
                className="button primary full"
                disabled={
                  busy ||
                  !canConfirmOrder(trip.quote, trip.version, consent, now)
                }
                onClick={onOrder}
              >
                Подтвердить демозаказ <ArrowUpRight size={17} />
              </button>
              {new Date(trip.quote.expires_at) <= now && (
                <>
                  <p className="attention">
                    Срок цены истёк. Проверьте её ещё раз.
                  </p>
                  <button
                    className="text-button"
                    disabled={busy}
                    onClick={onQuote}
                  >
                    Обновить цену
                  </button>
                </>
              )}
            </div>
          )}
          {!plan.validation.passed && (
            <p className="attention fine">
              Уточните блокирующие условия в проверках перед оформлением.
            </p>
          )}
          <p className="checkout-note">
            <ShieldCheck size={15} />
            <span>Бронирование и оплата имитируются</span>
          </p>
        </>
      )}
    </section>
  );
}
function detailLabel(key: string) {
  const labels: Record<string, string> = {
    origin: "Откуда", destination: "Куда", return_origin: "Откуда обратно", return_destination: "Куда обратно",
    stops: "Пересадок", mode: "Транспорт", duration_hours: "В пути, ч",
    outbound_departure: "Отправление", outbound_arrival: "Прибытие", return_departure: "Отправление обратно", return_arrival: "Прибытие обратно",
    passengers: "Пассажиров", pet_limit_kg: "Вес питомца до, кг", refundable: "С возвратом", baggage_included: "Багаж включён", price_basis: "Что включено в цену",
    adults: "Взрослых", children_ages: "Возраст детей", room_capacity: "Вместимость номера", checkin_at: "Заселение", checkout_at: "Выезд",
    nights: "Ночей оплачено", requested_nights: "Ночей запрошено", extra_night: "Дополнительная ночь включена", rooms: "Номеров", capacity: "Мест",
    meal: "Питание", reception_24h: "Круглосуточная стойка", location: "Расположение", mandatory_fees_included: "Обязательные сборы включены",
    baggage_buffer_minutes: "Время на багаж, мин", duration_minutes: "Длительность трансфера, мин", hotel_arrival: "Прибытие в отель",
    return_pickup: "Трансфер обратно", return_terminal_arrival: "Прибытие к терминалу обратно", terminal_buffer_minutes: "Запас до отправления, мин",
    child_seats: "Детских кресел", private: "Индивидуальный трансфер",
  };
  return labels[key] ?? "Дополнительное условие";
}
function detailValue(key: string, value: unknown): string {
  if (value == null) return "Не подтверждено";
  if (typeof value === "boolean") return value ? "Да" : "Нет";
  if (Array.isArray(value)) return value.length ? value.join(", ") : "Нет";
  if (typeof value === "string") {
    if (/^\d{4}-\d{2}-\d{2}T/.test(value)) return dateTime(value);
    const names: Record<string, string> = {
      moscow: "Москва", "saint-petersburg": "Санкт-Петербург", kazan: "Казань", sochi: "Сочи", kaliningrad: "Калининград", yerevan: "Ереван", istanbul: "Стамбул", antalya: "Анталья", hurghada: "Хургада",
      flight: "Самолёт", train: "Поезд", breakfast: "Завтрак", all_inclusive: "Всё включено", center: "В центре", beach: "У пляжа",
    };
    if (value === "any") return key === "meal" ? "Без питания" : "Без предпочтений";
    return names[value] ?? value;
  }
  return String(value);
}
