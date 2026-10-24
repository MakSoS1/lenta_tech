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
                      <dd>
                        {typeof value === "object"
                          ? JSON.stringify(value)
                          : typeof value === "boolean"
                            ? value
                              ? "Да"
                              : "Нет"
                            : String(value ?? "Неизвестно")}
                      </dd>
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
                <CircleCheck size={16} /> Запрос отправлен
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
    mode: "Транспорт",
    departure_at: "Отправление",
    arrival_at: "Прибытие",
    return_departure_at: "Отправление обратно",
    return_arrival_at: "Прибытие обратно",
    refundable: "С возвратом",
    pet_allowed: "Разрешён питомец",
    max_pet_kg: "Вес питомца до, кг",
    meal: "Питание",
    nights: "Ночей",
    rooms: "Номеров",
    checkin: "Заселение",
    checkout: "Выезд",
    stars: "Звёзды",
    location: "Расположение",
    duration_hours: "В пути, ч",
    early_checkin: "Раннее заселение",
    baggage: "Багаж",
    checkin_time: "Время заселения",
    checkout_time: "Время выезда",
  };
  return labels[key] ?? key.replaceAll("_", " ");
}
