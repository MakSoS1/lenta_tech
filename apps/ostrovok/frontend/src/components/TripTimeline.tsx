import { CalendarDays } from "lucide-react";
import type { Plan } from "../types";
export function dateTime(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat("ru-RU", {
        day: "numeric",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
      }).format(date);
}
export default function TripTimeline({ plan }: { plan: Plan }) {
  return (
    <section className="panel timeline">
      <div className="section-line">
        <h2>Всё по порядку</h2>
        <CalendarDays size={20} />
      </div>
      <p className="muted">Одна поездка — все стыковки перед глазами.</p>
      <ol>
        {plan.timeline.map((event, index) => (
          <li key={`${event.at}-${index}`}>
            <span className="timeline-dot" />
            <time>{dateTime(event.at)}</time>
            <div>
              <h3>{event.label}</h3>
              <p>{event.detail}</p>
            </div>
          </li>
        ))}
      </ol>
      <p className="fine">
        Время отображается в часовом поясе вашего устройства.
      </p>
    </section>
  );
}
