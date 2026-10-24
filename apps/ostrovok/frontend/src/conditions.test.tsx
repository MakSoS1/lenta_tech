import { expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import Checkout from "./components/Checkout";
import type { Plan, TripState } from "./types";
it("renders actual server condition fields in Russian", () => {
  const plan = {components: [{offer_id: "one", kind: "transport", title: "Дорога", total_minor: 10000, details: {mode:"flight", meal:"any", location:"center", origin:"moscow", return_terminal_arrival:"2026-11-07T10:00:00+03:00", checkin_at:"2026-11-07T15:00:00+03:00", pet_limit_kg:8, children_ages:[7,10]}, source:{observed_at:"2026-10-24T00:00:00Z", url:"", kind:"synthetic"}, expires_at:"2026-11-08T00:00:00Z"}], total_minor:10000, validation:{passed:true}} as unknown as Plan;
  const trip = {version:1, quote:null, order:null} as TripState;
  const html = renderToStaticMarkup(<Checkout trip={trip} plan={plan} busy={false} onQuote={()=>{}} onOrder={()=>{}} onService={()=>{}} service={null}/>);
  for (const text of ["Самолёт", "Без питания", "В центре", "Москва", "Прибытие к терминалу обратно", "Заселение", "Вес питомца до, кг", "7, 10"]) expect(html).toContain(text);
  for (const raw of [">flight<", ">any<", ">center<", "return terminal arrival", "2026-11-07T"]) expect(html).not.toContain(raw);
});
