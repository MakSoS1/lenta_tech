import {
  ArrowUpRight,
  Check,
  Clock3,
  Hotel,
  MapPin,
  Plane,
  TrainFront,
  CarFront,
  CircleCheck,
  CircleHelp,
} from "lucide-react";
import type { Offer, Plan, TripState } from "../types";
import { formatMoney, isPassingCheck } from "../behavior";
export const componentNames = {
  transport: "Дорога туда и обратно",
  hotel: "Проживание целиком",
  transfer: "Трансферы в обе стороны",
};
export function OfferIcon({ offer }: { offer: Offer }) {
  return offer.kind === "hotel" ? (
    <Hotel size={18} />
  ) : offer.kind === "transfer" ? (
    <CarFront size={18} />
  ) : String(offer.details.mode ?? offer.details.transport).includes(
      "train",
    ) ? (
    <TrainFront size={18} />
  ) : (
    <Plane size={18} />
  );
}
export function SourceBadge({ offer }: { offer: Offer }) {
  return (
    <span
      className="source-badge"
      title={`Источник: ${offer.source.name}. Наблюдение: ${offer.source.observed_at}`}
    >
      <span />
      {offer.source.kind === "synthetic"
        ? "Демо-каталог"
        : offer.source.kind} · {offer.source.name}
    </span>
  );
}
export default function TripComparison({
  trip,
  busy,
  onSelect,
}: {
  trip: TripState;
  busy: boolean;
  onSelect: (id: string) => void;
}) {
  return (
    <section aria-labelledby="comparison-heading">
      <div className="results-heading">
        <div>
          <div className="section-eyebrow">СОБРАНО ПОД ВАШИ УСЛОВИЯ</div>
          <h2 id="comparison-heading">Есть куда отправиться</h2>
        </div>
        <span className="count-label">{trip.plans.length} варианта</span>
      </div>
      <div className="plan-list">
        {trip.plans.map((plan, index) => (
          <PlanCard
            key={plan.plan_id}
            plan={plan}
            index={index}
            selected={trip.selected_plan_id === plan.plan_id}
            busy={busy}
            onSelect={onSelect}
          />
        ))}
      </div>
    </section>
  );
}
function PlanCard({
  plan,
  index,
  selected,
  busy,
  onSelect,
}: {
  plan: Plan;
  index: number;
  selected: boolean;
  busy: boolean;
  onSelect: (id: string) => void;
}) {
  return (
    <article
      className={`plan-card ${selected ? "selected" : ""}`}
      data-testid="plan-card"
    >
      <div className={`destination-art art-${plan.destination.id}`}>
        <div className="art-orbit" />
        <MapPin className="art-marker" size={35} />
        <span className="destination-country">{plan.destination.country}</span>
        <span className="destination-name">{plan.destination.name}</span>
        <div className="card-tag">
          {selected ? (
            <>
              <Check size={12} /> Ваш выбор
            </>
          ) : index === 0 ? (
            "01 / Первый вариант"
          ) : (
            `0${index + 1} / Альтернатива`
          )}
        </div>
      </div>
      <div className="plan-body">
        <div className="card-title-row">
          <div>
            <h3>{plan.title}</h3>
            <p className="useful">
              <Clock3 size={13} />
              {plan.useful_hours} ч на месте
            </p>
          </div>
          <div className="plan-price">
            {formatMoney(plan.total_minor)}
            <span>за всю поездку</span>
          </div>
        </div>
        <p className="card-hotel">
          {plan.components.find((offer) => offer.kind === "hotel")?.title}
        </p>
        <div className="included">
          {plan.components.map((offer) => (
            <span key={offer.offer_id}>
              <OfferIcon offer={offer} />
              {offer.kind === "transport"
                ? "Дорога"
                : offer.kind === "hotel"
                  ? "Отель"
                  : "Трансферы"}
            </span>
          ))}
        </div>
        {plan.reasons.length > 0 && <p className="reason">{plan.reasons[0]}</p>}
        {plan.tradeoffs.length > 0 && (
          <p className="tradeoff">
            <span>Компромисс:</span> {plan.tradeoffs[0]}
          </p>
        )}
        <details className="plan-notes">
          <summary>Состав и все ограничения</summary>
          <ul>
            {plan.components.map((offer) => (
              <li key={offer.offer_id}>
                {offer.title} — {formatMoney(offer.total_minor)}
              </li>
            ))}
            {plan.reasons.map((text, index) => (
              <li key={`reason-${index}`}>{text}</li>
            ))}
            {plan.tradeoffs.map((text, index) => (
              <li key={`tradeoff-${index}`}>{text}</li>
            ))}
          </ul>
        </details>
        <div className="card-footer">
          <span className="demo-label">Демонстрационные цены</span>
          <button
            className={`button ${selected ? "selected-button" : "primary"}`}
            disabled={busy}
            onClick={() => onSelect(plan.plan_id)}
          >
            {selected ? "Выбрано" : "Выбрать поездку"}
            {selected ? <Check size={15} /> : <ArrowUpRight size={15} />}
          </button>
        </div>
      </div>
    </article>
  );
}
export function Validation({ plan }: { plan: Plan }) {
  const issues = plan.validation.issues;
  return (
    <details className="validation panel inset">
      <summary>
        <CircleCheck size={17} />
        <strong>Проверки поездки</strong>
        <span className={plan.validation.passed ? "good" : "attention"}>
          {plan.validation.passed ? "Пройдены" : "Нужны уточнения"}
        </span>
      </summary>
      <div className="validation-list">
        {issues.length ? (
          issues.map((issue, index) => (
            <p key={`${issue.rule_id}-${index}`}>
              <span
                className={isPassingCheck(issue.status) ? "good" : "attention"}
              >
                {isPassingCheck(issue.status) ? (
                  <CircleCheck size={15} />
                ) : (
                  <CircleHelp size={15} />
                )}
              </span>
              <span>
                {issue.message}
                <small>
                  {issue.rule_id} · {issue.status}
                </small>
              </span>
            </p>
          ))
        ) : (
          <p className="muted">Все серверные проверки пройдены.</p>
        )}
      </div>
    </details>
  );
}
