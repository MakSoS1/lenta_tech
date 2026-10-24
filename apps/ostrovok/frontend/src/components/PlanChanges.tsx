import { GitCompareArrows } from "lucide-react";
import type { TripState } from "../types";
import { formatMoney } from "../behavior";
export default function PlanChanges({ delta }: { delta: TripState["delta"] }) {
  if (!delta) return null;
  return (
    <section className="delta">
      <div className="section-line">
        <h3>
          <GitCompareArrows size={18} /> Что изменилось
        </h3>
        {delta.price_delta_minor != null && (
          <strong>
            {delta.price_delta_minor > 0 ? "+" : ""}
            {formatMoney(delta.price_delta_minor)}
          </strong>
        )}
      </div>
      {delta.summary.map((text, index) => (
        <p key={index}>{text}</p>
      ))}
      <div className="delta-meta">
        <span>Сохранено компонентов: {delta.preserved_offer_ids.length}</span>
        <span>Переподобрано: {delta.invalidated_offer_ids.length}</span>
      </div>
    </section>
  );
}
